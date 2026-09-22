#!/usr/bin/env bash
# download_datasets.sh
# =====================
# Baixa os datasets públicos usados para testes iniciais do pipeline,
# enquanto o dataset próprio (coleta de campo) não está pronto.
#
# Rode a partir da raiz do projeto (cattle-monitor/). Cria tudo dentro
# de data/, que já está no .gitignore - nada aqui deve ser versionado.
#
# Uso:
#   bash scripts/download_datasets.sh            # baixa os 3 disponíveis
#   bash scripts/download_datasets.sh 8calves     # só um dataset específico
#   bash scripts/download_datasets.sh cbvd5
#   bash scripts/download_datasets.sh beca
#
# Pré-requisitos por dataset (o script avisa e pula se faltar algo):
#   8-Calves -> git, git-lfs
#   CBVD-5   -> kaggle CLI autenticado (~/.kaggle/kaggle.json)
#   BECA     -> curl, jq

set -e
DATA_DIR="data"
mkdir -p "$DATA_DIR"

WHAT="${1:-all}"

# ------------------------------------------------------------------
# 8-Calves (Fang et al., 2025) - HuggingFace, via git-lfs
# ------------------------------------------------------------------
download_8calves() {
  echo "=== 8-Calves ==="
  if ! command -v git-lfs >/dev/null 2>&1; then
    echo "AVISO: git-lfs não encontrado. Instale com:"
    echo "  sudo apt-get install git-lfs && git lfs install"
    echo "Pulando 8-Calves."
    return
  fi

  DEST="$DATA_DIR/8-calves"
  if [ -d "$DEST" ]; then
    echo "já existe: $DEST (pulei o clone; apague a pasta se quiser refazer)"
  else
    # --depth 1: não precisamos do histórico do repo, só do conteúdo atual.
    # Usando HTTPS em vez de SSH (git@hf.co:...) para não depender de chave
    # SSH cadastrada na conta do Hugging Face.
    git clone --depth 1 https://huggingface.co/datasets/tonyFang04/8-calves "$DEST"
  fi

  if [ -f "$DEST/make_dataset.sh" ]; then
    echo "Rodando make_dataset.sh (script oficial do dataset)..."
    (cd "$DEST" && bash make_dataset.sh)
  else
    echo "AVISO: make_dataset.sh não encontrado em $DEST — confira manualmente."
  fi

  echo "8-Calves pronto em $DEST"
  echo "(O ambiente de benchmark oficial deles - conda_requirements.txt / "
  echo " pip_requirements.txt dentro de $DEST - é OPCIONAL: só precisa disso"
  echo " se for reproduzir o benchmark deles. Pro seu tracker, o ambiente"
  echo " 'cattle' (environment.yml da raiz) já deve bastar.)"
}

# ------------------------------------------------------------------
# CBVD-5 (Li et al., 2024) - Kaggle
# ------------------------------------------------------------------
download_cbvd5() {
  echo "=== CBVD-5 ==="
  if ! command -v kaggle >/dev/null 2>&1; then
    echo "AVISO: kaggle CLI não encontrado. Instale com:"
    echo "  pip install kaggle"
    echo "E configure ~/.kaggle/kaggle.json (gerado em kaggle.com/settings)."
    echo "Pulando CBVD-5."
    return
  fi

  DEST="$DATA_DIR/cbvd-5"
  if [ -d "$DEST" ] && [ "$(ls -A "$DEST" 2>/dev/null)" ]; then
    echo "já existe e não está vazio: $DEST (pulei; apague se quiser refazer)"
  else
    mkdir -p "$DEST"
    kaggle datasets download -d fandaoerji/cbvd-5cow-behavior-video-dataset -p "$DEST" --unzip
  fi
  echo "CBVD-5 pronto em $DEST"
}

# ------------------------------------------------------------------
# BECA (Zhang et al., 2025) - Figshare, via API (descobre os arquivos
# do artigo em tempo real, em vez de fixar uma URL que pode mudar)
# ------------------------------------------------------------------
download_beca() {
  echo "=== BECA ==="
  if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
    echo "AVISO: precisa de curl e jq. Instale com:"
    echo "  sudo apt-get install curl jq"
    echo "Pulando BECA."
    return
  fi

  DEST="$DATA_DIR/beca"
  mkdir -p "$DEST"
  ARTICLE_ID=29425316   # DOI 10.6084/m9.figshare.29425316

  echo "Consultando API do Figshare (artigo $ARTICLE_ID)..."
  FILES_JSON=$(curl -s "https://api.figshare.com/v2/articles/${ARTICLE_ID}/files")

  if [ -z "$FILES_JSON" ] || [ "$FILES_JSON" = "[]" ]; then
    echo "AVISO: não consegui listar arquivos automaticamente."
    echo "Baixe manualmente em: https://doi.org/10.6084/m9.figshare.29425316"
    return
  fi

  echo "$FILES_JSON" | jq -c '.[]' | while read -r file; do
    NAME=$(echo "$file" | jq -r '.name')
    URL=$(echo "$file" | jq -r '.download_url')
    OUT="$DEST/$NAME"
    if [ -f "$OUT" ]; then
      echo "já existe: $OUT"
    else
      echo "baixando: $NAME"
      curl -L -o "$OUT" "$URL"
    fi
  done

  echo "BECA pronto em $DEST (contém as subpastas BECA-D e BECA-L, ou um"
  echo "arquivo compactado com elas dentro - confira e extraia se necessário)"
}

# ------------------------------------------------------------------
# CattleBehaviours6 (Liu et al., 2025) - AINDA NÃO DISPONÍVEL
# ------------------------------------------------------------------
note_cattlebehaviours6() {
  echo "=== CattleBehaviours6 ==="
  echo "PENDENTE: o paper (arXiv 2510.09203) diz que o dataset será liberado"
  echo "'upon acceptance of the paper' - ainda em preprint, sem link real."
  echo "Verifique de novo mais adiante, ou contate os autores:"
  echo "  andrew.dowsey@bristol.ac.uk (autor correspondente)"
}

case "$WHAT" in
  8calves) download_8calves ;;
  cbvd5)   download_cbvd5 ;;
  beca)    download_beca ;;
  all)
    download_8calves
    echo ""
    download_cbvd5
    echo ""
    download_beca
    echo ""
    note_cattlebehaviours6
    ;;
  *)
    echo "Uso: bash scripts/download_datasets.sh [8calves|cbvd5|beca|all]"
    exit 1
    ;;
esac
