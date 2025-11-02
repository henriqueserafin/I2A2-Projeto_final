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

### Vídeo da apresentação
https://youtu.be/FLDeX20uX04

---

### Diagrama de Sequencia do projeto:
[![](https://mermaid.ink/img/pako:eNqtVttu20YQ_ZUBX0QhMiPqbj4EKKwqSGsnhp0GRSGAWJEjaRFyl9ldCpIMf0zQh35AP0E_1uFNkm1GQlv7QbZXs2dmzpyZ2QcrkCFanqXxW4oiwDFnC8XiqQD6YYGRCn7T6e674rI4S5gyPOAJEwbujUIWR9yAPVFSGBRh86XVT4JFXLOQoOyYceEkmxqrWyUD1IXZ7zfXLw1uZBbMp6s7sD-TISqKrs7bAikQuL6-Afs9xlzwGqMvFFGYuUIN9u0mpDMevL1DSl2TeXGhyvvi3bs3dZl64DowYVtIk0iyEEIJTH1L-UqCTRm04HY8aYFM4UPMFhiXYdQhZR7qWPKg48CYawqdgYSkpCimDCUEMoaGlqkK0J_zCBsFfh0O4dfDdx34gorPecAgYMESwWZapzGW_63YlsvmSeB6ZnoO_LzmM4RGVVcRSsdxGmBr4-iEC4FqzzSLDEyidC0PlT_h8c0zqXjQZw5cLVnMKor8dRz5QR6NsZsHxGc3Lwjtop6ZAUHeISlOMAh5YKBBRdAY-iEzrHE-xpMK82BI8IXJU-C8qpU52GMZpHm1D4EfZXPSx4ncRhldUsy5IsZWOcjur92fZYMXnxhpLGtCMn5bSPh82rVNSgWaVQVSqfBloHwpctEeF6f27qkSzQ4lahhcG99In5HpZovnK1SPOSTMiSReTNlwcULCvmZiQeFz0TzPQM38Icb3-S_yIz-IOJk5XKzkV7QLP8fgL0FOEHF5TASJIZFCI3XaL_efPoI2iovFEfb_1q7b3meTS1c5-S-78vwKCnXdo5Ri2lCRPHTFqgT9jyV2O7Nc_itURHE-WvMGt3M_fpjGyauy1d2zhULxYEkSDf0iB4M-yTbTOZfCbtL13d_64smYfw0ye8f6eDJtsoho7wecdhfNapaG3Phx5nyBuuwhGujVnP53PPcduGfR6rlPISFbAeSEkva1IRZOov9o9w72I4UOUPlESxoZTV70ciaZCu1TGzejq1rwBDas9tW4up1P4l9vP-gWvFe777QipSaOPrMZRuwM8A8IGTlUtyc7fM4zy2021q2WFSMNHh7Sa-whczC1zBJjnFoe_Rky9XVqTcUj2bHUyPuNCCzPqBRblpLpYml5c0Yzu2WlSSas8h23P0WqrFQ3xWMvf_O1LHoKWd6Dtba8_sAZjtxhd-i67W63M2hZG8tzu5eO2xuMBm7XHfTb7f5jy9pKSZhtZ9Dv9ru90eiy03HdS7eXg_2Rf1nEtFBZImV8eYGuZCoMoY76j_8AEm1ymA?type=png)](https://mermaid.live/edit#pako:eNqtVttu20YQ_ZUBX0QhMiPqbj4EKKwqSGsnhp0GRSGAWJEjaRFyl9ldCpIMf0zQh35AP0E_1uFNkm1GQlv7QbZXs2dmzpyZ2QcrkCFanqXxW4oiwDFnC8XiqQD6YYGRCn7T6e674rI4S5gyPOAJEwbujUIWR9yAPVFSGBRh86XVT4JFXLOQoOyYceEkmxqrWyUD1IXZ7zfXLw1uZBbMp6s7sD-TISqKrs7bAikQuL6-Afs9xlzwGqMvFFGYuUIN9u0mpDMevL1DSl2TeXGhyvvi3bs3dZl64DowYVtIk0iyEEIJTH1L-UqCTRm04HY8aYFM4UPMFhiXYdQhZR7qWPKg48CYawqdgYSkpCimDCUEMoaGlqkK0J_zCBsFfh0O4dfDdx34gorPecAgYMESwWZapzGW_63YlsvmSeB6ZnoO_LzmM4RGVVcRSsdxGmBr4-iEC4FqzzSLDEyidC0PlT_h8c0zqXjQZw5cLVnMKor8dRz5QR6NsZsHxGc3Lwjtop6ZAUHeISlOMAh5YKBBRdAY-iEzrHE-xpMK82BI8IXJU-C8qpU52GMZpHm1D4EfZXPSx4ncRhldUsy5IsZWOcjur92fZYMXnxhpLGtCMn5bSPh82rVNSgWaVQVSqfBloHwpctEeF6f27qkSzQ4lahhcG99In5HpZovnK1SPOSTMiSReTNlwcULCvmZiQeFz0TzPQM38Icb3-S_yIz-IOJk5XKzkV7QLP8fgL0FOEHF5TASJIZFCI3XaL_efPoI2iovFEfb_1q7b3meTS1c5-S-78vwKCnXdo5Ri2lCRPHTFqgT9jyV2O7Nc_itURHE-WvMGt3M_fpjGyauy1d2zhULxYEkSDf0iB4M-yTbTOZfCbtL13d_64smYfw0ye8f6eDJtsoho7wecdhfNapaG3Phx5nyBuuwhGujVnP53PPcduGfR6rlPISFbAeSEkva1IRZOov9o9w72I4UOUPlESxoZTV70ciaZCu1TGzejq1rwBDas9tW4up1P4l9vP-gWvFe777QipSaOPrMZRuwM8A8IGTlUtyc7fM4zy2021q2WFSMNHh7Sa-whczC1zBJjnFoe_Rky9XVqTcUj2bHUyPuNCCzPqBRblpLpYml5c0Yzu2WlSSas8h23P0WqrFQ3xWMvf_O1LHoKWd6Dtba8_sAZjtxhd-i67W63M2hZG8tzu5eO2xuMBm7XHfTb7f5jy9pKSZhtZ9Dv9ru90eiy03HdS7eXg_2Rf1nEtFBZImV8eYGuZCoMoY76j_8AEm1ymA)


### Licença

Este projeto está licenciado sob a Licença MIT. Veja o arquivo LICENSE para mais detalhes.

---


