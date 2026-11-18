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

- [ ] **Fase 0 — Seleção e dimensionamento de zonas estratégicas de câmeras**
  Cálculo de footprint por zona (comedouro, bebedouro, área de descanso) — geometria simples, não GA completo. Não depende de instalação — é o que *antecede* ela. (Antes era "otimização de cobertura total do galpão"; mudou — ver Seção 4, nota de Set/2026.)
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
| Câmeras (Fase 0) | Sourav e Peschel 2022 | Ferramenta auxiliar, não mais a abordagem central — útil só se alguma zona tiver geometria complexa (ver Seção 4) |
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

### [Set/2026] Pivot: câmeras zona-específicas em vez de cobertura total do galpão

**Contexto**: a conta de cobertura overhead contínua dos 600 m² do galpão (teto de
~3m) exigia de 35 a 175+ câmeras — inviável. O orientador propôs, de forma
independente, instalar câmeras em zonas funcionais de alto tráfego (comedouro,
bebedouro, área de descanso), aproveitando cada zona para capturar simultaneamente
(a) dataset de identificação (via tracklet, sem re-confirmar ID a cada frame) e
(b) clipe de vídeo rotulável de comportamento.

**Já fundamentado na literatura revisada** (não é lacuna nova):
- Rice e Costa (2021) — já citado — usa exatamente essa estratégia (4 câmeras no
  comedouro, 10 nas baias, 4 no bebedouro).
- Yu et al. (2024) — já citado — 3 câmeras em pontos de passagem, dataset de
  identificação construído de forma quase auto-supervisionada via tracklet.
- Nguyen et al. (2021) — já citado — câmera única no bebedouro, captura
  identidade + comportamento de hidratação do mesmo ponto.

**Quantas câmeras os trabalhos usam, de fato** (referência pra dimensionar o
projeto):

| Trabalho | Nº câmeras | Contexto |
|---|---|---|
| Fuentes et al. (2023) | 2 | galpão fechado |
| Guzhva et al. (2018) | 3 | área de espera |
| Yu et al. (2024) | 3 | pontos de passagem, 90 vacas |
| Noe et al. (2025) | 4 | 55 bovinos, 23,3×20 m |
| Abbas et al. (2025) | 6 | galpão vacas leiteiras |
| Aou et al. (2024) | 7 | galpão inteiro |
| Yamamoto et al. (2025) | 10 | galpão inteiro, 31 dias |
| Rice e Costa (2021) | 18 (4+10+4 zona-específicas) | free-stall completo |

Densidade câmera:rebanho — Sourav e Peschel (2022) sugerem 8-10 vacas/câmera
(ótimo teórico); Toulemonde et al. (2026) reportam ~17-23 vacas/câmera em
implantações reais. Útil para estimar nº total de câmeras a partir do tamanho
do rebanho, quando esse número for definido.

**Pendência em aberto com o orientador**: zonas cobrem bem alimentação,
hidratação e descanso — mas locomoção e socialização acontecem nos trajetos
*entre* zonas, fora do alcance das câmeras nessa configuração. Decidir se ficam
fora do escopo ou se entra uma zona de trânsito adicional.

**Sobre inovação** (pergunta direta do orientador: "por usar câmera já usada
em outros trabalhos, o projeto continua inovador?"):
Sim — a estratégia de câmera é infraestrutura, não a contribuição. A câmera
zona-específica já é técnica estabelecida (tabela acima). A inovação do
trabalho continua na integração completa do pipeline (identificação-gatilho +
tracking + classificação de comportamento em um único sistema, coisa que
nenhum trabalho revisado faz de ponta a ponta) e no dataset resultante
(identidade + trajetória + comportamento juntos, em confinamento tropical
brasileiro com Holstein — combinação ainda inexistente nos benchmarks
públicos). Não apresentar "câmeras em múltiplas zonas" como a inovação em si
na introdução/justificativa do TCC — um avaliador da área reconheceria isso
como técnica já estabelecida.

**TCC já atualizado** com essa mudança: Seções 3.2 (objetivo de cobertura),
4.5.1 (Aou et al. 2024 adicionado, Yamamoto/Yu detalhados, densidade
câmera:rebanho), 4.5.2 (reescrita central da decisão), 4.5.3 (overlap
qualificado), 5.1, Fase 0 e Fase 2 do Capítulo 6, Tabela 5 e Tabela 7,
referências (Aou et al. 2024 adicionado).

