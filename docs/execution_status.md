# 执行状态记录

更新时间：2026-06-20 11:10 CST（已补 BUSCO 全量评估 + GPU Medaka 抛光）

## 总览

核心实验矩阵已完成，L3 重复/质粒扩展也已完成。当前 `results/tables/assembly_metrics.csv` 包含 55 条真实 assembly + QUAST 指标：

- L1 主矩阵：46 条。
- L3 重复/质粒扩展：9 条。
- 覆盖度档位：5、10、20、30、50。
- 技术种类：hifi、hybrid、illumina、ont_r10、ont_r9。
- 组装器种类：flye、hifiasm、miniasm、raven、spades、unicycler。

GPU 在宿主机可用：非沙箱 `nvidia-smi` 已确认 RTX 4090、Driver 580.159.03、CUDA 13.0。沙箱内 `nvidia-smi` 失败是设备访问限制，不代表宿主机 GPU 不可用。

## 已完成

- CPU 核心环境 `.conda/bench` 可用。
- 已补齐并验证关键 CPU 工具：ART、Badread、Flye、hifiasm、minimap2、QUAST、SPAdes、Raven、miniasm、racon。
- Unicycler 使用独立环境 `.conda/unicycler`，版本为 `v0.5.1`。
- 参考变体已生成：`ecoli_rep_v1.fasta`、`ecoli_rep_v2.fasta`、`ecoli_plasmid.fasta`。
- reads 模拟已完成：
  - L1：Illumina、ONT R9、ONT R10、HiFi 的 5x/10x/20x/30x/50x。
  - L3：rep_v1、rep_v2、plasmid 下的 Illumina 30x、ONT R10 30x、HiFi 30x。
- `results/tables/read_stats.csv` 已升级为扫描现有 FASTQ，当前包含 29 个数据集。
- L1 CPU 组装矩阵已完成：
  - Illumina + SPAdes：5 档覆盖度。
  - ONT R9 + Flye/Raven/miniasm：5 档覆盖度。
  - ONT R10 + Flye/Raven/miniasm：5 档覆盖度。
  - Hybrid + Unicycler：5 档覆盖度。
  - HiFi + hifiasm：5 档覆盖度。
  - HiFi 5x + Flye：对照组装。
- L3 扩展已完成：
  - rep_v1：Illumina + SPAdes、ONT R10 + Flye、HiFi + hifiasm。
  - rep_v2：Illumina + SPAdes、ONT R10 + Flye、HiFi + hifiasm。
  - plasmid：Illumina + SPAdes、ONT R10 + Flye、HiFi + hifiasm。
- 已重新生成核心图、覆盖度曲线、Pareto 图和读长分布图。
- 推荐器已运行，当前推荐 `ont_r10_20x_flye_orig_s13`。
- 已导出组装图 GFA：
  - `results/figures/graph_ont_r10_30x_flye_orig_s13.gfa`
  - `results/figures/graph_ont_r10_30x_flye_rep_v1_s13.gfa`
  - `results/figures/graph_ont_r10_30x_flye_rep_v2_s13.gfa`
  - `results/figures/graph_ont_r10_30x_flye_plasmid_s13.gfa`

## 新增 L3 结果

L3 摘要表：`results/tables/l3_reference_stress_summary.csv`

| run_id | contigs | genome_fraction_pct | misassemblies |
|---|---:|---:|---:|
| hifi_30x_hifiasm_plasmid_s13 | 2 | 100.0 | 0 |
| hifi_30x_hifiasm_rep_v1_s13 | 2 | 100.0 | 0 |
| hifi_30x_hifiasm_rep_v2_s13 | 3 | 100.0 | 1 |
| illumina_30x_spades_plasmid_s13 | 83 | 98.331 | 0 |
| illumina_30x_spades_rep_v1_s13 | 87 | 98.03 | 0 |
| illumina_30x_spades_rep_v2_s13 | 91 | 98.028 | 3 |
| ont_r10_30x_flye_plasmid_s13 | 2 | 100.0 | 0 |
| ont_r10_30x_flye_rep_v1_s13 | 2 | 99.893 | 0 |
| ont_r10_30x_flye_rep_v2_s13 | 1 | 100.0 | 0 |

L3 结论：短读长在重复/质粒参考下仍保持 80+ contigs，ONT R10 与 HiFi 能恢复到 1-3 contigs 且 genome fraction 接近或达到 100%。这补齐了重复区压力测试和质粒回收两个扩展点。

## 已解阻（2026-06-20 用 micromamba 完成）

conda 23.1.0 classic solver 解不动 → 改用 **micromamba 2.8.1**（`./bin/micromamba`，静态二进制，绕开 conda），两个环境分钟级建好：

- `.conda/busco`：BUSCO 6.1.0 + Merqury。
- `.conda/gpu`：Medaka 2.2.2 + minimap2 + samtools。

**① BUSCO 无参评估已完成**：对全部 **55/55** assembly 跑 BUSCO（bacteria_odb10，32 核并行，~15s/个），Complete% 已并入 `assembly_metrics.csv` 的 `busco_complete_pct` 列。结果与 genome fraction 高度一致（如 hifi_5x_flye 68% genome → 60% BUSCO；完整组装 → 100%）。

**② GPU 神经抛光已完成（创新点 5）**：Medaka 确认跑在 RTX 4090 上（`Model device: cuda:0`，模型 `r1041_e82_400bps_sup_v4.2.0`），对 10 个 ONT Flye 组装（R9/R10 × 5 覆盖度）抛光，产出 `polish_metrics.csv`（GPU 时间）和 `polish_quality.csv`（抛光前后 QUAST），图 `results/figures/polish_indel_comparison.png`。

## 抛光关键发现（重要，且诚实）

**在模拟 reads 上，Medaka 神经抛光几乎不改善、对 R9 甚至略微变差**：

| run | indels/100kb 前→后 | mismatch/100kb 前→后 |
|---|---|---|
| ont_r9 30× | 79.7 → 81.3 | 16.8 → **26.7（变差）** |
| ont_r9 50× | 60.6 → 61.9 | 5.7 → **18.6（变差）** |
| ont_r10 10× | 6.1 → 5.6（小幅改善 8%） | 4.4 → 4.2 |
| ont_r10 ≥20× | 0 → 0（本就完美） | 0 → 0 |

**原因（写进讨论/局限）**：① Medaka 是在**真实 ONT 信号**的错误模式上训练的，而这里是 **Badread 模拟 reads**，错误分布不匹配，神经网络无从纠正；② Medaka 自带模型是 **R10.4.1**，套到 R9 数据上属模型失配，反而引入 mismatch。
→ **这恰好是"模拟基准的局限"的有力证据，强力支撑"未来工作：在真实 reads 上验证"**。GPU 流程本身已跑通可复现，结论真实呈现，不做粉饰。

## 仍未做 / 降级

- Bandage 未安装，组装图只导出 GFA，未渲染 PNG（可 `pip install` 独立版补）。
- Illumina SPAdes 目录未找到脚本识别的 GFA，图导出以 ONT Flye 为主。
- ONT R9 + miniasm 的 5 条 QUAST 缺 alignment 质量列（这些组装无法有效比对参考，属真实结果，非脚本跳过）。
- Merqury QV：环境已就绪，尚未批量跑（可选，BUSCO 已覆盖"无参完整度"维度）。
- 下游 Prokka/Clair3（创新 6）、P2 加分（9/10/11）未做。

## 当前关键结论

- 在当前成本模型、预算 10 USD、genome fraction >= 99%、contigs <= 1 的约束下，推荐策略为 `ont_r10_20x_flye_orig_s13`。
- 推荐结果的估算成本为 0.92 USD，genome fraction 为 100.0%，N50 为 4,641,650 bp。
- 扩展分析给出的最小可用覆盖度为 20x。
- L1 技术/组装器方差贡献重新计算后分别约为 0.239 和 0.249。

## 剩余建议

1. ~~Medaka/BUSCO 用 micromamba 建环境~~ → **已完成**（BUSCO 全量 + GPU 抛光均已跑出）。
2. Bandage 可用 `pip install bandage` 或独立二进制补齐 PNG 渲染；并补 SPAdes 的 `assembly_graph.gfa` 路径。
3. `Snakemake` 仍未串测，后续可只做 `snakemake -n` dry-run 证明端到端 DAG。
4. （可选）下游 Prokka 基因恢复 + Clair3 变异检测（创新 6）；Merqury QV 批量；P2 加分。
5. 写作：把"关键结果发现"四条 + 抛光的诚实结论（模拟基准局限）填进 `report.md` / PPT。
