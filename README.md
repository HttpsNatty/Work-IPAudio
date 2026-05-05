docker-compose up --build
# 🚀 IPA — Transcrição fonética automática

Aplicação leve com backend em Python (Flask) e frontend estático para converter áudio em transcrição fonética (IPA). O site está publicado em: https://work-ip-audio-riei.vercel.app

**Demo (produzido no Vercel):** https://work-ip-audio-riei.vercel.app

## Sobre

Este repositório contém o backend (`backend/`), o frontend estático (`frontend/`) e um modelo local em `ipa-whisper-base/`. O README foi atualizado para facilitar execução local e publicação no Vercel.

## Rápido — executar localmente

- Requisitos: Docker (recomendado) ou Python 3.9+ e pip.

1) Usando Docker (recomendado):

```bash
docker-compose up --build
```

2) Sem Docker (modo desenvolvedor):

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # macOS / Linux
pip install -r backend/requirements.txt
cd backend
python app.py
```

Para o frontend estático, você pode abrir `frontend/index.html` diretamente ou servir a pasta:

```bash
cd frontend
python -m http.server 8000
# Abra http://localhost:8000
```

## Deploy no Vercel

Recomendação: publicar o frontend estático no Vercel (mais simples) e manter o backend em um serviço de backend (Render, Railway, Heroku) se for necessário manter estado ou usar modelos pesados.

Opção A — Deploy apenas do frontend (rápido):

1. Instale o CLI do Vercel: `npm i -g vercel`.
2. No root do projeto ou dentro de `frontend/`, execute:

```bash
cd frontend
vercel --prod --name work-ip-audio-riei
```

3. Confirme as opções sugeridas pelo CLI (diretório público = `.`). Após o deploy, o site estará em `https://work-ip-audio-riei.vercel.app`.

Opção B — Backend + Frontend no Vercel (avançado):

- O Vercel tem suporte a Serverless Functions, mas empacotar um modelo grande (como em `ipa-whisper-base/`) geralmente não é viável em funções serverless.
- Se desejar, coloque apenas rotinas leves no `api/` do Vercel e mantenha o modelo em um provider com mais recursos.

## Estrutura do repositório

- `backend/` — Flask app e dependências (`requirements.txt`).
- `frontend/` — HTML, CSS e JS estáticos.
- `ipa-whisper-base/` — arquivos do modelo local (pesados).
- `docker-compose.yml` / `docker-compose.override.yml` — orquestração local.

## Notas importantes

- O diretório `ipa-whisper-base/` contém pesos grandes — não os envie a repositórios públicos sem usar LFS ou storage externo.
- Não execute push automático: mantenha controle sobre pushes de grandes arquivos.

## Contribuição

- Abra uma issue para discutir mudanças.
- Para alterar README ou documentação, crie uma branch e envie um PR.

---

**Desenvolvido por Natty**