# 答辩讲稿草稿

## A：数据与模拟

我们使用 E. coli K-12 MG1655 作为小型参考基因组，并在原始参考的基础上构造重复注入版本和含质粒版本。当前已经完成 Illumina 五档覆盖度、ONT R9 三档覆盖度和 HiFi 五档覆盖度的 reads 模拟。读长分布图显示 Illumina 固定在 150 bp，ONT R9 平均约 9.8 kbp，HiFi 平均约 15.1 kbp。

## B：组装方法

短读长计划使用 SPAdes，长读长计划使用 Flye、Raven、miniasm，HiFi 额外加入 hifiasm，混合策略计划使用 Unicycler。当前环境中已经真实跑通 HiFi+hifiasm 的 5x、10x、20x、30x、50x，以及 HiFi 5x+Flye 对照。所有成功组装结果都归一化为 `assembly.fasta`，并记录 RAM 和运行时间。

## C：评估与分析

评估不只看 N50，还看 genome fraction、mismatch、indel、misassembly 和资源消耗。当前已完成 QUAST 主表；BUSCO 和 Merqury 因依赖未安装暂未填充。结果显示 HiFi+hifiasm 在 5x 时 genome fraction 为 90.677%，10x 时达到 99.755% 但仍有 6 个 contig，20x 起达到单 contig 和 100% genome fraction。因此当前最小可用覆盖度是 20x。

## D：工程化与策略建议

项目使用统一配置文件驱动矩阵，并把模拟脚本改成可恢复执行：已有输出会跳过，长读长先写临时文件，成功后再替换。GPU 抛光和 Clair3 变异检测当前因为 NVIDIA driver 不可用而阻塞。最后通过成本模型和指标表给出预算约束下的测序策略建议：在当前数据和单 contig 约束下，推荐 HiFi 20x + hifiasm。
