# 第二轮执行计划（覆盖首轮停止策略）

项目根目录 `/data2/user/LocateMOT_GroundJEV`；沿用 `yestrack_diagnosis_20261101/analysis/`，seed=2025。只使用 TempRMOT*，不再寻找或实现 YesTrack-MOT，也不发资源请求。

1. R13 读取既有 summary，并用官方 HOTA.combine_sequences 合并逐表达式 alpha 数组，给出逐视频 HOTA、精度/召回归因。
2. R14 核实 γ 只过滤现有连续分数；先重评预指定 .6，再做 .3–.8 附表。仅按用户规则比较 .4 与 .6 冻结一个本地 γ。
3. R15 统计 0019 框坐标与 crop 最大偏移；不超过 10 px 保持坐标不变。
4. 无论复现差距如何继续下游，所有结果标为“相对本地基线”。先准备 GT 候选、A–H 多标签（F/G 直接由标注）、冻结 LLM 补齐与 100 条审计，再运行 GT referring H2/H3；优先校准探针，随后误差分解、上下文/联合打分/TRP 与错误样例。
5. 每一 GPU 阶段启动前在 runs.md 写 cohort、完整命令和以 R09=2.2h 为参考的耗时估计；超过 8h 先向用户询问。全项目最多四张物理 GPU，遵守资源登记和 25 GiB 临时特征缓存限制。
6. 官方权重和推理逻辑保持不变；新增代码仅在 analysis/。长任务只用一个阻塞命令等完成，不做模型层进度轮询。先验修正只使用可确认的发布权重负样本保留率，不以仓库默认值猜测真实训练配置。

以下为首轮计划的历史记录，停止策略已被第二轮明确撤销。

# YesTrack / Refer-KITTI-V2 诊断计划

项目根目录：`/data2/user/LocateMOT_GroundJEV`。
独立任务目录：`yestrack_diagnosis_20261101`。所有新增脚本、配置、日志和结果均放在本目录的 `analysis/`；官方代码单独克隆到 `analysis/upstream/YesTrack/`，不修改。

## 执行顺序与停止条件

1. 已阅读官方 `llm_eval_from_mot.py`、`llm_eval.py`、`crop_utils.py`、`eval_refer_kitti_mot.py`、GT 转换器和 README/USAGE。固定源代码 commit 与 seed，检查官方 V2 adapter、两种 tracker 候选、原始数据及官方 seqmap 的可用性。
2. 先按论文配置复现 V2 val 的两种 tracker（HOTA/DetA/AssA），再在 GT 候选上计算 referential Acc/Precision/Recall。使用仓库自带 TrackEval 和官方完整 seqmap，记录帧号映射、预测面积过滤、类别处理及空 GT 的汇总行为。
3. 任一 tracker 与论文相差超过 1.5 HOTA，立即停止下游分析，报告可定位的权重/配置/数据/协议差异。官方训练权重不可获得时不得以基座零样本或本地 OneJev adapter 替代；若需训练且条件不具备，先报告并向用户询问。
4. 复现通过后，按 A–H 多标签分类；F 仅从同一可见 GT 轨迹上相邻有效帧的标签切换计算，G 从空 GT 计算。关键词初分、LLM 补齐，固定 seed 抽 100 条人工审计。明确表达式占比和 GT 帧数占比的分母。
5. 用相同 TrackEval 协议计算 H1/H2/H3 及各类别整体替换的 ΔHOTA。多标签类别的收益不可相加；H2−H1 是换用 GT tracks 后的差值，包含跟踪与 referring 的相互作用。官方 `HOTA.eval_sequence` 对 GT 和预测都为空的序列返回 HOTA=0，因此 G 类单独的 H3 不适用“接近 100”的判断；保留官方数值并说明该边界，使用总体 H3 验证几何/ID/协议，用 G 类误报率和总体类别替换收益衡量无目标问题。
6. 完成上下文、同一 Qwen 主干的联合选项打分、TRP 切换窗口和校准四个探针。RMOT 允许多目标；联合打分需要保留多目标语义，不能直接把单选 argmax 的下降归因于模型。Refer-KITTI 阈值选择与 V2 迁移评估分别记录。
7. 每类抽 30 FP/30 FN 生成可视化；不足 30 时如实报告实际数量。产出完整 `REPORT.md` 与可重跑的 `runs.md`。

## 首轮冻结配置

主结果使用论文：320×320，frame→选择性 video，p∈[0.2,0.8)，video memory=4，TCP window=3/threshold=0.4/boost=0.3，TRP Δ=10，γ=0.4，seed=2025。官方源代码的 crop 默认额外 margin_ratio=0.2（每边增加 20%，裁剪前名义宽高为 1.4 倍）。

README 发布权重校准说明：V2 γ≈0.6；README 的示例 TCP window=6/TRP Δ=4。它们是另行标记的发布配置检查，不能静默代替论文参数，也不能用在 V2 上扫描得到的最好数字冒充固定参数复现。

当前阶段是 TempRMOT* 完整论文参数复现；不在门槛通过前生成类别结论或提升空间数字。GPU 启动前读取项目资源登记，合计最多四张物理 GPU，任务显式设置 CUDA_VISIBLE_DEVICES；不运行旧 U2 队列，临时特征缓存至多 25 GiB。长任务由一个阻塞 shell 命令等待，不进行模型层轮询。
