# 🚀 IPA — Transcrição fonética automática

Uma aplicação leve com backend em Python (Flask) e frontend estático para converter áudio em transcrição fonética (IPA). Ideal para testes locais com um modelo embarcado em `ipa-whisper-base`.

## ✨ Funcionalidades

- **Transcrição em IPA**: Converte áudio (.wav, .mp3, .ogg, .opus) em símbolos fonéticos.
- **Upload e reprodução**: Drag & drop ou seleção de arquivo, com player embutido.
- **Processamento local**: Integração com o modelo presente em `ipa-whisper-base/` (atenção ao tamanho dos pesos).
- **Interface moderna**: UI responsiva com tema escuro e feedback visual.
- **Docker-ready**: `docker-compose.yml` e `docker-compose.override.yml` prontos para desenvolvimento.

## 🛠️ Instalação

1. Clone este repositório:

```bash
git clone https://github.com/HttpsNatty/Work-IPAudio.git
cd Work-IPAudio
```

2. (Opcional) Usando Docker:

```bash
docker-compose up --build
```

3. (Opcional) Rodando local sem Docker:

```bash
python -m venv .venv
.venv\\Scripts\\activate    # Windows
source .venv/bin/activate     # macOS / Linux
pip install -r backend/requirements.txt
cd backend && python app.py
```

Abra o frontend em `http://localhost:3000` ou sirva `frontend/` estaticamente.

## ⚙️ Configuração

- Ajuste parâmetros e chaves (se houver) no `backend/` conforme necessário.
- `ipa-whisper-base/` contém os arquivos do modelo; para repositórios públicos prefira armazenar pesos em LFS ou storage externo.

> [!IMPORTANT]
> Verifique se `backend/requirements.txt` está instalado e se tem espaço suficiente para o modelo local.

## 📖 Como usar

1. Abra a UI em seu navegador.
2. Faça upload do arquivo de áudio via drag & drop ou clicando na área de upload.
3. Aguarde o processamento — a transcrição em IPA aparecerá na área de resultados.
4. Use o botão de copiar para exportar a transcrição.

## 🎨 Personalização

- Troque cores no `frontend/style.css` para adaptar a paleta.
- Se quiser trocar o modelo, substitua os arquivos em `ipa-whisper-base/` e ajuste `backend` conforme necessário.

---

*Desenvolvido por Natty com objetivo de aumentar a produtividade.*
