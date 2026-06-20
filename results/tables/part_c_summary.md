# Part C 组装质量初步结论

1. N50：ont_r10_30x_flye_rep_v2_s13 的 N50 最高（4,659,660 bp）。
2. 连续性：illumina_5x_spades_orig_s13 拼得最碎（1,296 个 contigs）。
3. 准确性：ont_r9_5x_flye_orig_s13 的错误最多，mismatches + indels 为 3620.93/100 kbp；ont_r9_5x_flye_orig_s13 的 mismatch 最高，ont_r9_5x_flye_orig_s13 的 indel 最高。
   注意：ont_r9_10x_miniasm_orig_s13、ont_r9_20x_miniasm_orig_s13、ont_r9_30x_miniasm_orig_s13、ont_r9_50x_miniasm_orig_s13、ont_r9_5x_miniasm_orig_s13 的错误指标缺失，未按 0 处理，也未参与错误率排名。
4. Hybrid 是否比单一 reads 更好：否，Hybrid 的 contig 数量只与最佳单一 reads 并列，且 N50 未超过 PacBio HiFi。
