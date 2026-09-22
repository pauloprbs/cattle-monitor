# Guia de Implementação — Monitoramento de Bovinos em Confinamento

> Documento de trabalho, não faz parte da proposta formal (TCC).
> Atualize os checkboxes conforme for avançando. Anexe este arquivo + o TCC (docx/pdf)
> no início de cada nova conversa para retomar o contexto sem gastar tokens reconstruindo tudo.

## Como usar isso numa nova conversa

Prompt sugerido para colar junto com os anexos:

> "Anexei o guia de implementação e a proposta de TCC. Quero continuar de onde parei —
> [descreva o que já fez ou o módulo em que quer focar agora]. Me ajude a avançar nisso."

---

## 1. Ordem de implementação dos módulos

Pensada para não depender da instalação física das câmeras — tudo até o item 4 roda com dado público.

- [ ] **Fase 0 — Otimização de posicionamento de câmeras**
  Simulação em cima do modelo 3D do galpão (40×15 m). Não depende de instalação — é o que *antecede* ela.
- [ ] **Arquitetura de software** (buffer circular, schema do banco, logging)
  Engenharia pura, testável com detecções sintéticas/mockadas.
- [ ] **Classificador de comportamento**
  Treinar em cima do CBVD-5 ou CattleBehaviours6 (ver seção 3).
- [ ] **Tracker (ByteTrack / DeepSORT)**
  Testar em cima do 8-Calves.
- [ ] **Detecção + identificação dorsal**
  Prototipar arquitetura com dataset público; trocar por fine-tune próprio quando houver imagens do galpão.

---

## 2. Artigos para leitura aprofundada (não só citação)

| Módulo | Artigo | Observação |
|---|---|---|
| Tracking (base) | Zhang et al. 2022 — ByteTrack | Vai implementar o algoritmo em si |
| Tracking (base) | ⚠️ SORT, DeepSORT (Wojke et al.), OC-SORT — **papers originais, ainda não levantados** | A proposta cita adaptações bovinas, não os originais — garimpar antes de codar |
| Tracking (longo prazo) | Wang et al. 2026 — tracking-by-classification | Arquitetura mais próxima do que foi proposto |
| Identificação | Menezes et al. 2025 — keypoints + SNN | Mais reproduzível; bom candidato à primeira implementação |
| Câmeras (Fase 0) | Sourav e Peschel 2022 | Algoritmo a ser portado diretamente |
| Anotação | Cao et al. 2025 | Pipeline de anotação semi-automática (YOLOv8 + ByteTrack) |
| Sequência de BBs | Rao et al. 2026 | Hiperparâmetros de janela (16–32 frames, 50% overlap, crop 224×224) |
| Comportamento (baseline) | Wu et al. 2021 — CNN-LSTM | Primeiro classificador funcional, antes do TimeSformer |
| Comportamento (avançado) | Liu et al. 2025 — Cattle-CLIP | Estratégia few-shot para desbalanceamento de classes |

---

## 3. Datasets públicos para testes iniciais

| Dataset | Bom para | Limitação | Status |
|---|---|---|---|
| **8-Calves** (Fang et al. 2025) | Tracker sob oclusão | Sem anotação comportamental nem ID biométrica | ✅ Disponível — `huggingface.co/datasets/tonyFang04/8-calves` |
| **CBVD-5** (Li et al. 2024, Kaggle) | Classificador de comportamento | Sem identidade persistente (formato AVA) | ✅ Disponível — `kaggle.com/datasets/fandaoerji/cbvd-5cow-behavior-video-dataset` |
| **BECA** (Zhang et al. 2025) | Prototipar arquitetura de Re-ID e degradação por tempo | Corte, não leiteiro; snapshot periódico, não vídeo contínuo | ✅ Disponível — `doi.org/10.6084/m9.figshare.29425316` |
| **CattleBehaviours6** (Liu et al. 2025) | Classificador de comportamento (mesma raça, Holstein) | Rebanho/instalação diferentes — cuidado com generalização | ❌ **Pendente** — paper em preprint (arXiv 2510.09203), dataset só será liberado "upon acceptance". Sem link real ainda. Revisitar mais adiante ou contatar `andrew.dowsey@bristol.ac.uk`. |

Script pronto pra baixar os três disponíveis: `scripts/download_datasets.sh` (dentro do repo `cattle-monitor`).
Uso: `bash scripts/download_datasets.sh` (todos) ou `bash scripts/download_datasets.sh beca` (um específico).

---

## 4. Notas e decisões (preencher ao longo do tempo)

- (adicione aqui achados, dificuldades, mudanças de escopo, decisões do orientador)
