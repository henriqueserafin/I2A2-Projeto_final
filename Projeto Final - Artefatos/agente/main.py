import streamlit as st
import os
import json
import re
import numpy as np
import cv2  # open cv
import pandas as pd
import pytesseract
import plotly.express as px
import xml.etree.ElementTree as ET
from PIL import Image
from rich import print
from dotenv import load_dotenv
from pdf2image import convert_from_bytes
from typing import Optional
import st_file_uploader as stf
# imports do langchain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, ValidationError

# Carrega o .env
load_dotenv(override=True)

### IMPORTANTE, adicione o caminho do tesseract ela pode ser achada aqui
#https://github.com/UB-Mannheim/tesseract/wiki

# cache da sessão pra não processar o mesmo arq dnv
if "processed_data" not in st.session_state:
    st.session_state["processed_data"] = None
if "last_uploaded_id" not in st.session_state:
    st.session_state["last_uploaded_id"] = None
if "file_uploader_key_id" not in st.session_state:
    st.session_state["file_uploader_key_id"] = 0

# Config do Tesseract //mudar para o seu caminho
TESSERACT_PATH = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
if 'TESSERACT_PATH' in os.environ:
    pytesseract.pytesseract.tesseract_cmd = os.environ['TESSERACT_PATH']
elif os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    pass # se nao achar, vai tentar usar o do PATH

# Config da página do Streamlit
st.set_page_config(
    page_title="Analisador de Documentos",
    layout="wide",
    initial_sidebar_state="collapsed"
)



# Pega a chave da API do Google
google_api_key = os.getenv("GOOGLE_API_KEY")
gemini_client = None # inicializa como nulo

if google_api_key:
    st.sidebar.info(f"Chave API carregada (parcial): {google_api_key[-4:]}...")
    try:
        # Conecta no LLM
        gemini_client = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", # o modelo mais simples para não consumir a api mt rápido
            google_api_key=google_api_key,
            temperature=0.1  # temp baixa pra ele nao inventar dados
        )
        st.session_state["llm_ready"] = True
    except Exception as e:
        st.error(f"Erro ao inicializar o modelo Gemini. Detalhes: {e}")
        st.session_state["llm_ready"] = False
else:
    st.error("Chave da API do Google não encontrada. Bota no .env")
    st.session_state["llm_ready"] = False



# Classes de uma nota fiscal

class Participante(BaseModel):
    """Sub-estrutura para Remetente e Receptor."""
    id_fiscal: str = Field(description="ID Fiscal (CNPJ ou CPF) da parte (apenas dígitos).")
    nome_completo: str = Field(
        description="Nome ou Razão Social completa.",
    )
    endereco_completo: str = Field(description="Endereço completo (Rua, Número, Bairro, Cidade, Estado).")
    inscricao_estadual: str = Field(description="Inscrição Estadual, se disponível.")


class TotaisValores(BaseModel):
    """Sub-estrutura para os Totais de Valores (Nível de Documento)."""
    base_calculo_principal: float = Field(description="Valor total da Base de Cálculo principal (ex: ICMS) do documento.")
    valor_total_principal: float = Field(description="Valor total do valor principal (ex: ICMS) destacado no documento.")
    valor_total_adicional: float = Field(description="Valor total do valor adicional (ex: IPI) destacado no documento.")
    valor_total_contribuicao_a: float = Field(description="Valor total da Contribuição A (ex: PIS) destacado no documento.")
    valor_total_contribuicao_b: float = Field(description="Valor total da Contribuição B (ex: COFINS) destacado no documento.")
    valor_outras_despesas: float = Field(description="Valor total de outras despesas acessórias (frete, seguro, etc.).")
    valor_aprox_taxas_total: float = Field(description="Valor aproximado total das taxas.")


class ItemDocumento(BaseModel):
    descricao: str = Field(description="Nome ou descrição completa do produto/serviço.")
    quantidade: float = Field(description="Quantidade do item, convertida para um valor numérico (float).")
    valor_unitario: float = Field(description="Valor unitário do item.")
    valor_total: float = Field(description="Valor total da linha do item.")
    codigo_operacao: str = Field(description="Código de Operação (ex: CFOP) associado ao item, se disponível.")
    codigo_tributario: str = Field(description="Código de Situação Tributária (ex: CST/CSOSN) do item, se disponível.")
    valor_aprox_taxas: float = Field(description="Valor aproximado das taxas incidentes sobre este item (Lei da Transparência).")


class DocumentoProcessado(BaseModel):
    numero_controle: str = Field(description="Número de Controle (ex: Chave de Acesso) do documento (44 dígitos), se presente.")
    modelo_documento: str = Field(description="Modelo do documento (Ex: NF-e, NFS-e, Cupom).")
    data_emissao: str = Field(description="Data de emissão do documento no formato DD-MM-AAAA.") 
    valor_total_nota: float = Field(description="Valor total FINAL do documento (somatório de tudo).")
    tipo_operacao: str = Field(description="Descrição do tipo de operação (Ex: Venda de Mercadoria, Remessa para Armazém Geral).")

    remetente: Participante = Field(description="Dados completos do remetente (quem vendeu/prestou o serviço).")
    receptor: Participante = Field(description="Dados completos do receptor (quem comprou/recebeu o serviço).")
    totais_valores: TotaisValores = Field(description="Valores totais de taxas e despesas acessórias do documento.")
    itens: list[ItemDocumento] = Field(description="Lista completa de todos os produtos ou serviços discriminados no documento, seguindo o esquema ItemDocumento.")


#helpers e funções

def formatar_valor_br(valor):
    """Função auxiliar para formatar float como moeda brasileira (R$ X.XXX,XX)."""
    if valor is None or valor == 0.0:
        return "R$ 0,00"
    try:
        # gambiarra pra formatar BRL
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def safe_float(value):
    """Converte qualquer valor para float de forma segura, tratando Nones, strings e vírgulas."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        # pra nao quebrar convertendo numero q vem como texto
        return float(str(value).replace(',', '.').strip() or 0.0)
    except:
        return 0.0





def process_xml_content(xml_content: str) -> dict:
    """
    Processa o conteúdo XML de um documento (ex: NF-e) e extrai os dados diretamente
    para o formato de dicionário compatível com DocumentoProcessado.
    """
    # TIRA O NAMESPACE!! senao o find nao acha nada
    xml_content = xml_content.replace('xmlns="http://www.portalfiscal.inf.br/nfe"', '')
    root = ET.fromstring(xml_content)

    # helper pra achar tag
    def find_text(path, element=root, default=""):
        node = element.find(path)
        return node.text if node is not None else default

    # helper pra converter float (ja ta la em cima, mas o xml usa outra)
    def safe_float_xml(text):
        try:
            if isinstance(text, str):
                 text = text.replace(',', '.')
            return float(text)
        except (ValueError, TypeError):
            return 0.0

    # --- Dados Principais (infNFe) ---
    numero_controle = find_text('.//chNFe') or find_text('.//Id', default="").replace('NFe', '')
    data_emissao_raw = find_text('.//dhEmi') or find_text('.//dEmi')
    data_emissao = "" 
    if data_emissao_raw:
        data_emissao_iso = data_emissao_raw[:10] 
        try:
            # Tenta reformatar de AAAA-MM-DD para DD-MM-AAAA
            parts = data_emissao_iso.split('-')
            if len(parts) == 3:
                data_emissao = f"{parts[2]}-{parts[1]}-{parts[0]}" 
            else:
                data_emissao = data_emissao_iso 
        except Exception:
            data_emissao = data_emissao_iso 

    modelo_documento = find_text('.//mod')
    valores_tot = root.find('.//ICMSTot') 
    valor_total_nota = safe_float_xml(find_text('.//vNF', valores_tot))
    tipo_operacao = find_text('.//natOp')

    # --- Totais de Valores (imposto/ICMSTot) ---
    totais_valores = {
        'base_calculo_principal': safe_float_xml(find_text('.//vBC', valores_tot)),
        'valor_total_principal': safe_float_xml(find_text('.//vICMS', valores_tot)),
        'valor_total_adicional': safe_float_xml(find_text('.//vIPI', valores_tot)),
        'valor_total_contribuicao_a': safe_float_xml(find_text('.//vPIS', valores_tot)),
        'valor_total_contribuicao_b': safe_float_xml(find_text('.//vCOFINS', valores_tot)),
        'valor_outras_despesas': safe_float_xml(find_text('.//vOutro', valores_tot)),
        'valor_aprox_taxas_total': safe_float_xml(find_text('.//vTotTrib', valores_tot)),
    }

    # --- Remetente (emit) e Receptor (dest) ---
    def extract_participante(element_tag):
        element = root.find(f'.//{element_tag}')
        if element is None: return {}

        id_fiscal = find_text('.//CNPJ', element) or find_text('.//CPF', element)
        ender = element.find('.//enderEmit') or element.find('.//enderDest')

        endereco_completo = ""
        if ender is not None:
             logradouro = find_text('.//xLgr', ender)
             numero = find_text('.//nro', ender)
             bairro = find_text('.//xBairro', ender)
             municipio = find_text('.//xMun', ender)
             uf = find_text('.//UF', ender)
             endereco_completo = f"{logradouro}, {numero} - {bairro} - {municipio}/{uf}".strip() if all([logradouro, numero, municipio, uf]) else ""

        return {
            'id_fiscal': id_fiscal,
            'nome_completo': find_text('.//xNome', element),
            'endereco_completo': endereco_completo,
            'inscricao_estadual': find_text('.//IE', element),
        }

    remetente = extract_participante('emit') # pega os dados do emitente
    receptor = extract_participante('dest') # pega os dados do destinatario

    # --- Itens (det) ---
    itens = []
    for det in root.findall('.//det'):
        prod = det.find('.//prod')
        imposto = det.find('.//imposto')

        codigo_tributario = ""
        imposto_node = imposto.find('.//ICMS') 
        if imposto_node is not None:
            # Procura por qualquer nó que contenha CST ou CSOSN
            for imposto_subnode in imposto_node:
                if 'CST' in imposto_subnode.tag:
                    codigo_tributario = find_text('.//CST', imposto_subnode)
                    break
                elif 'CSOSN' in imposto_subnode.tag:
                    codigo_tributario = find_text('.//CSOSN', imposto_subnode)
                    break

        v_aprox_taxas = 0.0
        if imposto.find('.//impostoTrib') is not None:
             v_aprox_taxas = safe_float_xml(find_text('.//vTotTrib', imposto.find('.//impostoTrib')))

        itens.append({
            'descricao': find_text('.//xProd', prod),
            'quantidade': safe_float_xml(find_text('.//qCom', prod)),
            'valor_unitario': safe_float_xml(find_text('.//vUnCom', prod)),
            'valor_total': safe_float_xml(find_text('.//vProd', prod)),
            'codigo_operacao': find_text('.//CFOP', prod),
            'codigo_tributario': codigo_tributario,
            'valor_aprox_taxas': v_aprox_taxas,
        })

    # --- Montagem do Resultado Final ---
    result = {
        'numero_controle': numero_controle,
        'modelo_documento': modelo_documento,
        'data_emissao': data_emissao,
        'valor_total_nota': valor_total_nota,
        'tipo_operacao': tipo_operacao,
        'remetente': remetente,
        'receptor': receptor,
        'totais_valores': totais_valores,
        'itens': itens,
    }

    return result # devolve o dicionario pronto


def run_ocr_on_file(source_file):
    """
    Processa o arquivo carregado (JPG/PNG ou PDF) e retorna o texto extraído
    usando Tesseract OCR.
    """
    file_type = source_file.type
    source_file.seek(0) # rebobina o arquivo

    # config do tesseract
    ocr_config = '--oem 1 --psm 3' 

    full_text_list = []
    images_to_process = []
    img_to_display = None

    if "pdf" in file_type:
        try:
            # pdf vira imagem (lista de imagens)
            images_to_process = convert_from_bytes(source_file.read())

            if not images_to_process:
                return "ERRO_CONVERSAO: Não foi possível converter o PDF em imagem."

            img_to_display = images_to_process[0] # pega a primeira pagina pra mostrar

        except Exception as e:
            return f"ERRO_PDF: Verifique se 'poppler-utils' está instalado. Detalhes: {e}"

    elif "image" in file_type:
        try:
            img_to_display = Image.open(source_file)
            images_to_process.append(img_to_display)
        except Exception as e:
            return f"ERRO_IMAGEM: Falha na abertura da imagem. Detalhes: {e}"

    else:
        return "ERRO_TIPO_INVALIDO: Tipo de arquivo não suportado (apenas PDF, PNG, JPG)."

    if images_to_process:
        try:
            for i, image_pil in enumerate(images_to_process):
                img_for_ocr = image_pil
                
                # aqui q o tesseract le
                text = pytesseract.image_to_string(img_for_ocr, lang='por', config=ocr_config)
                
                full_text_list.append(f"\n--- INÍCIO PÁGINA {i+1} ---\n\n" + text)

            if img_to_display is not None:
                st.session_state["image_to_display"] = img_to_display # salva pra mostrar na tela

            return "\n".join(full_text_list)

        except pytesseract.TesseractNotFoundError:
            return "ERRO_TESSERACT: O Tesseract não está instalado ou configurado no PATH."
        except Exception as e:
            return f"ERRO_PROCESSAMENTO: Falha no OCR ou pré-processamento. Detalhes: {e}"

    return "ERRO_FALHA_GERAL: Falha desconhecida na extração de texto."


def enrich_and_validate_extraction(parsed_data: dict, ocr_text: str) -> tuple[dict, list]:
    """
    1. Tenta arrumar dados faltantes com Regex.
    2. Valida se a soma dos itens bate com o total.
    """
    enriched_data = parsed_data.copy()
    itens_processados = []
    total_itens_calculado = 0.0
    messages = [] 

    # Regex pra achar cfop (4 digitos) e cst (2-3 digitos)
    cod_op_pattern = re.compile(r'\b(\d{4})\b')
    cod_trib_pattern = re.compile(r'\b(0\d{2}|[1-9]\d{1,2})\b')

    # 1. Fallback com Regex
    if ocr_text:
        messages.append(("info", "Iniciando enriquecimento heurístico para códigos (Cod. Operação, Cod. Tributário)."))

        for item in enriched_data.get('itens', []):
            item_desc_lower = item['descricao'].lower()

            try:
                item['valor_total'] = float(item['valor_total'])
            except (TypeError, ValueError):
                 item['valor_total'] = 0.0

            total_itens_calculado += item['valor_total']

            # se n achou cfop, tenta regex
            if not item.get('codigo_operacao') or len(item['codigo_operacao']) != 4:
                match = cod_op_pattern.search(item_desc_lower)
                if match:
                    item['codigo_operacao'] = match.group(1)
                    messages.append(("success", f"✅ Cod. Operação do item '{item['descricao'][:20]}...' preenchido via Regex: **{item['codigo_operacao']}**"))

            # se n achou cst, tenta regex
            if not item.get('codigo_tributario') or len(item['codigo_tributario']) < 2:
                match = cod_trib_pattern.search(item_desc_lower)
                if match:
                    item['codigo_tributario'] = match.group(1)
                    messages.append(("success", f"✅ Cod. Tributário do item '{item['descricao'][:20]}...' preenchido via Regex: **{item['codigo_tributario']}**"))

            itens_processados.append(item)

        enriched_data['itens'] = itens_processados

    # 2. Validação dos Totais
    messages.append(("info", "Iniciando pós-validação de consistência de totais."))

    valor_total_nota = enriched_data.get('valor_total_nota', 0.0)
    tolerance = 0.01 # 1 centavo de tolerancia

    soma_itens_formatada = formatar_valor_br(total_itens_calculado)
    total_nf_formatado = formatar_valor_br(valor_total_nota)

    # ve se a conta fecha (soma dos itens == total da nota)
    if abs(total_itens_calculado - valor_total_nota) <= tolerance:
        messages.append(("success", f"👍 **Consistência Aprovada!** O somatório dos itens é consistente com o Valor Total do Documento. Soma dos Itens: {soma_itens_formatada} | Total Doc: {total_nf_formatado}"))
    else:
        messages.append(("error", f"🚨 **ALERTA DE INCONSISTÊNCIA!** O somatório dos itens extraídos é diferente do Valor Total do Documento extraído. | Soma dos Itens: {soma_itens_formatada} | Total Doc: {total_nf_formatado} | Recomendação: Verifique a qualidade do OCR ou edite os valores manualmente."))

    return enriched_data, messages


def check_for_missing_data(parsed_data: dict) -> list:
    """Ve se ta faltando coisa importante (remetente, receptor, valor, itens)"""
    warnings = []

    remetente = parsed_data.get('remetente', {})
    receptor = parsed_data.get('receptor', {})

    if not remetente.get('id_fiscal') or not remetente.get('nome_completo'):
        warnings.append("❌ Dados completos do Remetente estão faltando ou ilegíveis.")

    if not receptor.get('id_fiscal') or not receptor.get('nome_completo'):
        warnings.append("❌ Dados completos do Receptor estão faltando ou ilegíveis.")

    valor_total_nota = parsed_data.get('valor_total_nota', 0.0)
    if valor_total_nota <= 0.0:
        warnings.append("❌ O 'Valor Total do Documento' está zerado (R$ 0,00).")

    if not parsed_data.get('itens'):
        warnings.append("❌ A lista de Itens/Produtos está vazia.")

    return warnings


# O prompt principal pro Gemini
system_prompt = (
    "Você é um Agente de Extração de Dados especializado em documentos, incluindo documentos eletrônicos (DANFE) e cupons/recibos."
    "Sua função é ler o texto bruto (OCR) de documentos e extrair os dados em formato JSON, "
    "obedecendo rigorosamente o schema Pydantic fornecido."
    "Siga estas regras estritas:"
    "1. **Documentos de Consumidor (Recibos):** Esses documentos muitas vezes listam 'CONSUMIDOR NAO INFORMADO'. Neste caso, preencha os campos `id_fiscal` e `nome_completo` do `receptor` com a string 'CONSUMIDOR NAO INFORMADO'."
    "2. **Correção Ortográfica Contextual (CRÍTICO):** O texto de entrada é gerado por um OCR e contém erros de grafia comuns. Tente corrigir esses erros de grafia na `descricao` do `ItemDocumento`, usando o contexto do texto e o português correto, antes de incluí-lo no JSON. Caso não consiga inferir qual é a palavra, mantenha o valor original"
    "3. **Extração de Texto Bruto:** Se um campo estiver faltando ou for ilegível no texto OCR, preencha-o com uma string vazia (''), mas *nunca* invente dados (exceto pela Regra 1)."
    "4. **Valores Numéricos (CRÍTICO - FORMATO BRASILEIRO):** Converta todos os valores monetários e quantias (que usam ponto como milhar e vírgula como decimal, ex: 1.234,56) para o formato `float` americano (ponto como separador decimal, sem separador de milhar, ex: 1234.56). "
    "   - **Atenção:** Remova o separador de milhar (ponto ou espaço) e substitua a vírgula (,) pelo ponto (.)." # ISSO DA MTO PROBLEMA!!
    "5. **Datas:** Converta todas as datas para o formato estrito 'DD-MM-AAAA'." 
    "6. **Número de Controle:** O número deve ser uma string de 44 dígitos (apenas números). Se for um recibo, o número pode estar em blocos, junte-os."
    "7. **Tabelas de Itens:** Preste **MÁXIMA ATENÇÃO** à leitura correta das colunas. O campo `valor_total` deve ser o **Valor Total do Item/Produto**, e **NÃO** o Valor Principal ou outro valor."
    "8. **Saída:** O resultado final deve ser **SOMENTE** o JSON, sem qualquer texto explicativo ou markdown adicional." # importante
)

# Pega as instrucoes do Pydantic
parser = PydanticOutputParser(pydantic_object=DocumentoProcessado)

# Monta o prompt final
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        ("human", "Extraia os dados do documento no seguinte texto OCR. Retorne apenas o JSON. {format_instructions}\n\nTexto OCR:\n{text_to_analyze}"),
    ]
).partial(format_instructions=parser.get_format_instructions())


#Exibição dos dados

def render_results_dashboard(parsed_data: dict, source: str, ocr_text: Optional[str] = None):
    """Funcao monstro pra desenhar a tela principal com os resultados."""

    st.header(f"📊 Painel de Análise do Documento ({source})")
    
    if ocr_text:
        with st.expander("🕵️ Ver Texto OCR Bruto (Enviado ao LLM)", expanded=False):
            st.info("Este é o texto exato que o Tesseract extraiu e enviou para o LLM. Se estiver ilegível, o problema é o OCR.")
            st.code(ocr_text, language="text")

    # logica de validacao so pro ocr
    if source == "LLM/OCR" and ocr_text:
        parsed_data, audit_messages = enrich_and_validate_extraction(parsed_data, ocr_text)

        st.markdown("---")
        st.subheader("🛠️ Auditoria Pós-Extração (Regras)")

        for msg_type, msg_text in audit_messages:
            if msg_type == "info":
                st.info(msg_text)
            elif msg_type == "success":
                st.success(msg_text, icon="✔")
            elif msg_type == "error":
                st.error(msg_text, icon="❌")
            else:
                 st.markdown(msg_text)

        st.markdown("---")

    # Checa se falta dado critico
    quality_warnings = check_for_missing_data(parsed_data)

    if quality_warnings:
        st.error(f"⚠️ Atenção: Foram encontradas **{len(quality_warnings)} informações críticas faltando** ou zeradas. Verifique os detalhes abaixo:")
        
        with st.expander("Clique para ver os detalhes das inconsistências", expanded=True): 
            for warning in quality_warnings:
                st.markdown(warning)
    else:
        st.success("🎉 Verificação de Qualidade: Nenhuma informação crítica obrigatória faltando (Remetente, Receptor, Valor, Itens).")

    st.markdown("---") 

    # os cartoes la de cima (KPIs)
    st.subheader("📈 Resumo dos Dados (KPIs)")

    valores_data = parsed_data.get('totais_valores', {})
    valor_total = parsed_data.get('valor_total_nota', 0.0)
    total_itens = len(parsed_data.get('itens', []))
    total_taxas = valores_data.get('valor_aprox_taxas_total', 0.0)
    total_principal = valores_data.get('valor_total_principal', 0.0)
    total_adicional = valores_data.get('valor_total_adicional', 0.0)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Valor Total do Documento", formatar_valor_br(valor_total).replace("R$ ", ""))
    kpi2.metric("Nº de Itens", total_itens) 
    kpi3.metric("Total Principal / Adicional", f"{formatar_valor_br(total_principal).replace('R$ ', '')} / {formatar_valor_br(total_adicional).replace('R$ ', '')}")
    kpi4.metric("V. Aprox. Taxas", formatar_valor_br(total_taxas).replace("R$ ", ""))

    st.markdown("---")

    # Infos gerais
    st.subheader("Informações Principais do Documento")

    col_data, col_valor, col_modelo, col_natureza = st.columns(4)

    col_data.metric("Data de Emissão", parsed_data['data_emissao'])
    col_valor.metric("Valor Total do Documento", formatar_valor_br(parsed_data.get('valor_total_nota', 0.0)).replace("R$ ", ""))
    col_modelo.metric("Modelo Documento", parsed_data['modelo_documento'])
    with col_natureza:
        st.markdown("**Tipo de Operação**")
        st.info(parsed_data['tipo_operacao'])

    st.markdown("---")
    st.markdown("#### 🔑 **Número de Controle**")
    st.code(parsed_data['numero_controle'], language="text")
    st.markdown("---")

    # Remetente e Receptor (escondido)
    col_emitente, col_destinatario = st.columns(2)

    with col_emitente.expander("🏢 Detalhes do Remetente", expanded=False):
        remetente_data = parsed_data.get('remetente', {})
        st.json(remetente_data)

    with col_destinatario.expander("👤 Detalhes do Receptor", expanded=False):
        receptor_data = parsed_data.get('receptor', {})
        st.json(receptor_data)

    # Tabela de Itens
    st.subheader("🛒 Itens do Documento")

    itens_list = parsed_data.get('itens', [])
    df_itens = pd.DataFrame()

    if itens_list:
        # joga os itens num dataframe do pandas
        df_itens = pd.DataFrame(itens_list)

        for col in ['quantidade', 'valor_unitario', 'valor_total', 'valor_aprox_taxas']:
            df_itens[col] = pd.to_numeric(df_itens[col], errors='coerce').fillna(0.0).astype(float)

        # a tabela principal
        st.dataframe(
            df_itens,
            column_order=["descricao", "quantidade", "valor_unitario", "valor_total", "codigo_operacao", "codigo_tributario", "valor_aprox_taxas"],
            column_config={
                "descricao": st.column_config.Column("Descrição do Item", width="large"),
                "quantidade": st.column_config.NumberColumn("Qtde"),
                "valor_unitario": st.column_config.NumberColumn("Valor Unit.", format="R$ %.2f"),
                "valor_total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                "codigo_operacao": st.column_config.Column("Cod. Op."),
                "codigo_tributario": st.column_config.Column("Cod. Trib."),
                "valor_aprox_taxas": st.column_config.NumberColumn("V. Aprox. Taxas", format="R$ %.2f")
            },
            hide_index=True,
            width='stretch' 
        )

        # --- Seção de Gráficos ---
        st.markdown("### 📊 Análise de Agrupamento")
        
        selected_chart = st.radio(
            "Escolha o Tipo de Análise:", 
            ('Cod. Operação (Valor)', 'Proporção de Custos', 'Valor por Item'), 
            horizontal=True,
            key='chart_selector' 
        )
        
        # logica do grafico 1
        if selected_chart == 'Cod. Operação (Valor)':
            
            df_cod_op_process = df_itens[['codigo_operacao', 'valor_total']].copy()
            df_cod_op_process['Cod_Operacao'] = df_cod_op_process['codigo_operacao'].astype(str).str.strip().replace(['nan', '', 'None', ''], 'SEM COD. OP.')
            df_cod_op = df_cod_op_process.groupby('Cod_Operacao', dropna=False)['valor_total'].sum().reset_index()
            df_cod_op.columns = ['Cod. Operacao', 'Valor Total']
            
            fig = px.bar(
                df_cod_op, 
                x='Cod. Operacao', 
                y='Valor Total', 
                text='Valor Total',
                labels={'Valor Total': 'Valor Total (R$)', 'Cod. Operacao': 'Código de Operação'},
                color='Cod. Operacao',
                title='Valor de Produtos/Serviços agrupado por Cód. de Operação'
            )
            
            fig.update_xaxes(type='category') 
            fig.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside')
            fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
            st.plotly_chart(fig, use_container_width=True)

        # logica do grafico 2
        elif selected_chart == 'Proporção de Custos':
            
            total_produtos = df_itens['valor_total'].sum() if not df_itens.empty else 0.0 
            
            valores_destacados = (
                safe_float(valores_data.get('valor_total_principal')) +
                safe_float(valores_data.get('valor_total_adicional')) +
                safe_float(valores_data.get('valor_total_contribuicao_a')) +
                safe_float(valores_data.get('valor_total_contribuicao_b'))
            )
            
            valor_aprox_taxas_nota = safe_float(valores_data.get('valor_aprox_taxas_total'))
            
            if valores_destacados < 0.01 and valor_aprox_taxas_nota > 0.01:
                total_valores_secundarios = valor_aprox_taxas_nota
                valor_label = 'Taxas (Valor Aproximado do Documento)'
            else:
                total_valores_secundarios = valores_destacados
                valor_label = 'Valores Secundários (Principal, Adicional, Contr. A/B)'
    
            
            total_outras_despesas = (
                safe_float(valores_data.get('valor_frete')) + 
                safe_float(valores_data.get('valor_seguro')) + 
                safe_float(valores_data.get('valor_outras_despesas'))
            )
            
            df_custos = pd.DataFrame({
                'Componente': [
                    'Valor dos Produtos/Serviços', 
                    valor_label, 
                    'Frete/Seguro/Outras Despesas'
                ],
                'Valor': [total_produtos, total_valores_secundarios, total_outras_despesas]
            })
            
            df_custos = df_custos[df_custos['Valor'].round(2) > 0.01]
            
            valor_total_calculado = df_custos['Valor'].sum()
            valor_total_nota = safe_float(parsed_data.get('valor_total_nota', 0.0))
            
            titulo_grafico = 'Composição do Valor Total do Documento'
            
            if abs(valor_total_calculado - valor_total_nota) > 1.0:
                 titulo_grafico += f" (Aviso: Soma dos Componentes (R$ {valor_total_calculado:,.2f}) difere do Total (R$ {valor_total_nota:,.2f}))"
            
            # grafico de rosquinha
            fig = px.pie(
                df_custos,
                names='Componente',
                values='Valor',
                title=titulo_grafico,
                hole=.4  
            )
            
            fig.update_traces(textinfo='percent+label', marker=dict(line=dict(color='#000000', width=1)))
            fig.update_layout(showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

        
        # logica do grafico 3
        elif selected_chart == 'Valor por Item':
            
            df_item_val = df_itens.groupby('descricao')['valor_total'].sum().reset_index()
            df_item_val.columns = ['Descrição', 'Valor Total']
            df_item_val = df_item_val.sort_values(by='Valor Total', ascending=False).head(10)

            fig = px.bar(
                df_item_val, 
                x='Valor Total', 
                y='Descrição', 
                orientation='h', # grafico deitado
                text='Valor Total',
                labels={'Valor Total': 'Valor Total (R$)', 'Descrição': 'Produto/Serviço'},
                color='Descrição',
                title='Top 10 Produtos/Serviços por Valor Total'
            )
            
            fig.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside')
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("Nenhum item ou serviço foi encontrado no documento para gerar a tabela.")

    # Totais
    st.markdown("---")
    st.subheader("💰 Totais de Valores e Despesas (Nível do Documento)")

    total_taxas_calculado = df_itens['valor_aprox_taxas'].sum() if not df_itens.empty else 0.0
    total_taxas_extraido_direto = valores_data.get('valor_aprox_taxas_total', 0.0)

    # Logica pra decidir qual valor de taxa mostrar
    if total_taxas_calculado > 0.0:
        total_final_taxas = total_taxas_calculado
        fonte_taxas = " (Soma dos Itens)"
    elif total_taxas_extraido_direto > 0.0:
        total_final_taxas = total_taxas_extraido_direto
        fonte_taxas = " (Total do Documento)"
    else:
        total_final_taxas = 0.0
        fonte_taxas = ""

    col_icms, col_ipi, col_pis, col_cofins, col_outras, col_aprox = st.columns(6)

    col_icms.metric("Base Principal", formatar_valor_br(valores_data.get('base_calculo_principal')))
    col_icms.metric("Total Principal", formatar_valor_br(valores_data.get('valor_total_principal')))
    col_ipi.metric("Total Adicional", formatar_valor_br(valores_data.get('valor_total_adicional')))
    col_pis.metric("Total Contr. A", formatar_valor_br(valores_data.get('valor_total_contribuicao_a')))
    col_cofins.metric("Total Contr. B", formatar_valor_br(valores_data.get('valor_total_contribuicao_b')))
    col_outras.metric("Outras Despesas", formatar_valor_br(valores_data.get('valor_outras_despesas')))
    col_aprox.metric(f"Total V. Aprox. Taxas{fonte_taxas}", formatar_valor_br(total_final_taxas))

    # caixinha pra editar manual se o LLM falhar
    principal_zerado = valores_data.get('valor_total_principal', 0.0) <= 0.0
    adicional_zerado = valores_data.get('valor_total_adicional', 0.0) <= 0.0

    if (principal_zerado or adicional_zerado) and source == "LLM/OCR":
        st.markdown("---")
        st.subheader("✍️ Edição Manual de Valores")
        st.info("O Agente LLM não conseguiu extrair os valores detalhados. Se o documento contém esses valores, insira-os abaixo para corrigir o JSON de download.")

        principal_val = str(valores_data.get('valor_total_principal', 0.0))
        adicional_val = str(valores_data.get('valor_total_adicional', 0.0))
        contr_a_val = str(valores_data.get('valor_total_contribuicao_a', 0.0))
        contr_b_val = str(valores_data.get('valor_total_contribuicao_b', 0.0))

        col_edit_icms, col_edit_ipi, col_edit_pis, col_edit_cofins = st.columns(4)
        key_suffix = source.lower().replace("/", "_")

        principal_manual = col_edit_icms.text_input("Valor Principal", value=principal_val, key=f"manual_val_princ_{key_suffix}")
        adicional_manual = col_edit_ipi.text_input("Valor Adicional", value=adicional_val, key=f"manual_val_adic_{key_suffix}")
        contr_a_manual = col_edit_pis.text_input("Contr. A", value=contr_a_val, key=f"manual_val_ca_{key_suffix}")
        contr_b_manual = col_edit_cofins.text_input("Contr. B", value=contr_b_val, key=f"manual_val_cb_{key_suffix}")

        try:
            # Atualiza o dicionário principal (parsed_data)
            parsed_data['totais_valores']['valor_total_principal'] = float(principal_manual.replace(",", "."))
            parsed_data['totais_valores']['valor_total_adicional'] = float(adicional_manual.replace(",", "."))
            parsed_data['totais_valores']['valor_total_contribuicao_a'] = float(contr_a_manual.replace(",", "."))
            parsed_data['totais_valores']['valor_total_contribuicao_b'] = float(contr_b_manual.replace(",", "."))
            st.success("Valores atualizados para o JSON de download.")
        except ValueError:
            st.error("Erro: Certifique-se de que os valores inseridos manualmente são números válidos.")

    # Botoes de Download
    st.markdown("---")
    st.subheader("⬇️ Downloads dos Dados Extraídos")
    col_json_btn, col_csv_btn = st.columns(2)

    try:
        nome_curto = parsed_data['remetente']['nome_completo'].split(' ')[0]
        data_emissao_nome = parsed_data['data_emissao']
    except (KeyError, IndexError, TypeError):
        nome_curto = "extraido"
        data_emissao_nome = "data_desconhecida"

    # botao de download JSON
    json_data = json.dumps(parsed_data, ensure_ascii=False, indent=4)
    col_json_btn.download_button(
        label="⬇️ Baixar JSON COMPLETO da Extração",
        data=json_data,
        file_name=f"doc_{data_emissao_nome}_{nome_curto}.json",
        mime="application/json",
        use_container_width=True
    )

    if not df_itens.empty:
        df_csv = df_itens.rename(columns={
            "descricao": "Descricao_Produto",
            "quantidade": "Quantidade",
            "valor_unitario": "Valor_Unitario",
            "valor_total": "Valor_Total_Item",
            "codigo_operacao": "Cod_Operacao",
            "codigo_tributario": "Cod_Tributario",
            "valor_aprox_taxas": "Valor_Aprox_Taxas"
        })

        cols_para_formatar = ["Quantidade", "Valor_Unitario", "Valor_Total_Item", "Valor_Aprox_Taxas"]
        
        for col in cols_para_formatar:
            if col in df_csv:
                df_csv[col] = df_csv[col].apply(lambda x: f"{x:.2f}".replace('.', ',')) # troca ponto por virgula pro excel

        # botao de download CSV (excel BR usa ;)
        csv_data = df_csv.to_csv(
            index=False,
            sep=';',
            encoding='utf-8-sig' 
        )
        
        col_csv_btn.download_button(
            label="⬇️ Baixar Itens em CSV (Formato ABNT)",
            data=csv_data,
            file_name=f"itens_{data_emissao_nome}_{nome_curto}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    else:
        col_csv_btn.download_button(
            label="⬇️ Baixar Itens em CSV (Sem Itens)",
            data="",
            file_name="sem_itens.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=True,
            help="Não há itens no documento para baixar."
        )

    # JSON de debug
    with st.expander("Ver JSON Bruto Completo (DEBUG)", expanded=False):
         st.json(parsed_data)


# =======================================================================
# --- 6. LÓGICA PRINCIPAL DO APP (STREAMLIT) ---
# =======================================================================

st.title("Analisador de Documentos do grupo IAgentes") # Titulo

if not st.session_state.get("llm_ready"):
    st.error("⚠️ Erro: A chave 'GOOGLE_API_KEY' não foi encontrada. O Extrator de PDF/Imagem (LLM/OCR) está desativado. Apenas a extração de XML está funcional.")

st.sidebar.header("Upload de Arquivo")

# o botao de upload
# O NOVO CÓDIGO (SOLUÇÃO RECOMENDADA):
source_file = stf.pt.file_uploader(  # <-- Mude de 'st.' para 'stf.pt.'
    label="Escolha o Documento:", 
    type=["png", "jpg", "jpeg", "pdf", "xml"]
    #... mantenha seus outros parâmetros como 'label_visibility'
)

# botao de limpar
if st.sidebar.button("🔄 Limpar e Iniciar Novo Processo", type='primary', use_container_width=True):
    keys_to_clear = ["processed_data", "processed_source", "ocr_text", "image_to_display"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state["file_uploader_key_id"] += 1 # truque pra resetar o uploader
    st.rerun() 

# --- Logica principal ---
if source_file is not None:

    uploaded_file_identifier = source_file.name + str(source_file.size)

    if st.session_state.get("last_uploaded_id") != uploaded_file_identifier:
        st.session_state["processed_data"] = None # limpa o cache se o arq for novo
        st.session_state["last_uploaded_id"] = uploaded_file_identifier
        
    # se ja processou, so mostra
    if st.session_state["processed_data"] is not None:
        parsed_data = st.session_state["processed_data"]
        source = st.session_state["processed_source"]
        ocr_text = st.session_state.get("ocr_text", None) 

        render_results_dashboard(parsed_data, source=source, ocr_text=ocr_text)

    # se nao, processa agora
    elif st.session_state["processed_data"] is None:
        
        file_type = source_file.type

        with st.spinner(f"Processando arquivo ({source_file.name})..."):

            # --- FLUXO XML (mais facil) ---
            if "xml" in file_type:
                source_file.seek(0)
                xml_content = source_file.read().decode('utf-8')
                parsed_data = process_xml_content(xml_content) 

                if "error" in parsed_data:
                    st.error(parsed_data["error"])
                else:
                    try:
                        DocumentoProcessado(**parsed_data) # Valida com Pydantic
                        
                        st.session_state["processed_data"] = parsed_data
                        st.session_state["processed_source"] = "XML"
                        
                        render_results_dashboard(parsed_data, source="XML")
                    except ValidationError as ve:
                        st.error(f"Erro de Validação Pydantic ao ler XML: {ve}")
                        st.info("O XML foi processado, mas falhou na validação do esquema. Use o JSON Bruto para debug.")
                        render_results_dashboard(parsed_data, source="XML")

            # --- FLUXO PDF/IMAGEM (usa LLM) ---
            elif st.session_state.get("llm_ready"):

                # 1. Roda OCR
                text_to_analyze = run_ocr_on_file(source_file)
                response = None

                if text_to_analyze.startswith("ERRO_"):
                     st.error(f"Erro na extração de texto (OCR): {text_to_analyze}")
                else:
                    if "image_to_display" in st.session_state:
                        st.sidebar.success("Arquivo carregado e OCR concluído.")
                        with st.sidebar.expander("🔎 Visualizar Documento"):
                            st.image(st.session_state["image_to_display"], caption="Documento Processado", use_container_width=True)

                    try:
                        # 2. Chama o Gemini
                        final_prompt = prompt.format(text_to_analyze=text_to_analyze)
                        response = gemini_client.invoke(final_prompt)
                        
                        # 3. Valida com Pydantic
                        extracted_data_model = parser.parse(response.content)

                        parsed_data = extracted_data_model.model_dump()

                        # Salva no cache
                        st.session_state["processed_data"] = parsed_data
                        st.session_state["processed_source"] = "LLM/OCR"
                        st.session_state["ocr_text"] = text_to_analyze 

                        # 4. Mostra na tela
                        render_results_dashboard(parsed_data, source="LLM/OCR", ocr_text=text_to_analyze)

                    except ValidationError as ve:
                        st.error("Houve um erro de validação (Pydantic). O LLM pode ter retornado um JSON malformado.")
                        if response is not None:
                            with st.expander("Ver Resposta Bruta do LLM (JSON malformado)", expanded=True):
                                st.code(response.content, language='json')
                        st.warning(f"Detalhes do Erro: {ve}")

                    except Exception as e:
                        st.error(f"Houve um erro geral durante a interpretação pelo LLM. Detalhes: {e}")
                        if 'response' in locals() and response is not None:
                             with st.expander("Ver Resposta Bruta do LLM", expanded=False):
                                st.code(response.content, language='text')
                        with st.expander("Ver Texto OCR Bruto"):
                            st.code(text_to_analyze, language="text")
            else:
                st.warning("O arquivo é uma imagem/PDF, mas o processamento LLM está desativado (sem Google API Key).")
            
