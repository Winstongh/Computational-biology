# PPT 大纲

1. 标题：多代测序技术比较与小型基因组组装
2. 研究问题：短读长、ONT、HiFi 在小型基因组组装中的取舍
3. 为什么 30x 单点结果不够：缺少覆盖度梯度和成本拐点
4. 实验矩阵与统一 run-id：`config/matrix.yaml` 和 `{tech}_{cov}x_{assembler}_{ref}_s{seed}`
5. A：参考变体与 reads 模拟结果
6. A：读长分布与覆盖度统计
7. B：组装器封装与资源记录
8. C：QUAST 指标体系和主表 schema
9. C：HiFi+hifiasm 五档覆盖度结果
10. C：覆盖度饱和曲线与最小可用覆盖度 20x
11. D：质量-成本 Pareto 与推荐策略
12. 工程化复现：可恢复模拟、标准 assembly 输出、图表自动生成
13. 当前限制：缺失工具、GPU driver 不可用、完整矩阵待补齐
14. 结论：当前推荐 HiFi 20x + hifiasm
