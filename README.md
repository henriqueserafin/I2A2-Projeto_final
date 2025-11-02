### Extrator de documentos fiscais

> Extrator de Documentos fiscais desenvolvido pelo grupo IAgentes para o projeto final do curso de Agentes Inteligentes

> 

---

### Requisitos

- Python 3.11+
- pip ou uv
- Conta e credenciais de API do gemini

---

### Instalação

### Usando pip

```bash
python -m venv .venv
source .venv\Scripts\activate  # no Linux: .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Usando uv (Recomendado)

```bash
uv run main.py
```

---

### Variáveis de ambiente

Crie um arquivo .env na raiz do projeto:

Coloque os valores:

```bash
# .env
GOOGLE_API_KEY=(SuaChaveAPI)
```

---

### Como executar

### Streamlit



```bash
streamlit run main.py
```


---

### Problemas comuns e soluções

- Porta em uso:

```bash
lsof -i :8501 | awk 'NR>1 {print $2}' | xargs kill -9
```

- Variáveis não carregadas:

```bash
export $(grep -v '^#' .env | xargs)
```

---

### Licença

Este projeto está licenciado sob a Licença MIT. Veja o arquivo LICENSE para mais detalhes.

---
