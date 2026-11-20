## R54：video 路由核查及单参数 γ-LOSO 对照

本节按用户新指令追加。旧 R53 开 TCP 的实际候选运行已终止、显存释放，旧输出归档保留，后续不续跑。

### 路由到底读取哪个分数

在 R09/R17 的 frame→选择性 video 分支中，路由读取**本次新推理的 frame 原始分数**：

- 全量推理在 [877–886 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L877) 产生 frame 概率，[892 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L892) 把本次全部候选列为可精炼项。
- 跳过帧只对新 ID 推理，[938–944 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L938) 把这些新原始分数回填，并仅将 `new_indices` 列为可精炼项。旧 ID 虽复用了最终分数，也不参与 video 路由。
- [945–949 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L945) 在这些新鲜候选上测试 `[.2,.8)`；video 回填到 [1002–1003 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1002) 后，[1004–1017 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1004) 才执行 TCP。

**代码结论：当前参数路径下，TCP 开关不决定 video 调用集合；不会因开启 TCP 的 trace 而缺失去 TCP 重放所需的 video 分数。**原 GT 候选缓存对照依然有效。仍遵用户指定，实际候选另跑官方关闭 TCP 的直接验证，形成原生 V1。

### V1 只调 γ 的四折 LOSO

先于结果冻结 [R54 方案](plans/round3_gamma_control.json)。沿用 Δ10、固定 video 路由、无 TCP 的 V1 连续分数；每折只在其余三个视频用 pooled micro-F1 选择 γ∈{.1,.2,.3,.4,.5,.6,.7,.8,.9}，与 R52 HMM 的训练目标/阈值网格一致，仅拟合1个标量。留出序列的决策合并后由官方 TrackEval 计算 HOTA。固定 γ=.6 的 V1 仍为未调参参照。

| 留出序列 | 选定 γ | 训练三序列 micro-F1 |
|---|---:|---:|
| 0005 | 0.6 | 72.29% |
| 0011 | 0.6 | 71.28% |
| 0013 | 0.6 | 72.79% |
| 0019 | 0.7 | 76.90% |

| GT候选版本（全部Δ10） | HOTA | DetA | AssA | DetPr | DetRe | P | R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V1固定γ=.6 | 68.739 | 56.169 | 84.132 | 67.693 | 76.573 | 68.53% | 77.52% | 72.75% |
| V1单参数γ-LOSO | 68.035 | 55.534 | 83.357 | 70.244 | 72.490 | 71.03% | 73.31% | 72.15% |
| HMM三参数LOSO | 69.482 | 56.346 | 85.689 | 68.829 | 75.488 | 69.71% | 76.46% | 72.93% |

| 序列 | V1固定γ HOTA | γ-LOSO HOTA | HMM-LOSO HOTA | HMM−γ-LOSO |
|---|---:|---:|---:|---:|---:|
| 0005 | 74.562 | 74.562 | 75.021 | +0.459 |
| 0011 | 75.088 | 75.088 | 75.349 | +0.261 |
| 0013 | 71.595 | 71.595 | 70.179 | -1.416 |
| 0019 | 65.252 | 63.785 | 66.419 | +2.634 |

原 HMM 比固定γ V1 高 **0.743 HOTA**；单参数γ控制带来 **-0.704**，公平比较后 HMM−γ控制剩 **+1.447 HOTA**。

**判定：在冻结网格、相同LOSO目标下，单参数阈值未覆盖全部HMM增量；剩余差值如上，不能仅凭这四个序列声称显著或普遍的独立滤波收益。**

这里只比较预注册的训练目标与网格；未将完整 val 最佳γ当作LOSO结果，也未根据结果扩大网格。两条流程的训练自由度不同，结论属于这个对照，不是任意阈值/滤波器的理论证明。

切换和空帧对照：γ-LOSO在F类真→假后0–5帧错误率为65.63%，HMM-LOSO为75.06%（均3529条）；空GT帧误报率分别为16.97%和17.96%。因此HMM较高的HOTA不能解释为更快解除真→假锁存。

[完整数值](runs/R54_gamma_control/result.json) · [每折参数](runs/R54_gamma_control/parameters.json) · [训练网格](runs/R54_gamma_control/training_grid.csv) · [路由核查](runs/R54_gamma_control/routing_audit.json)

### 更正旧 R53 的进度与耗时外推

官方 [1184–1185 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1184) 只让 rank0 打印 `[OK]`。此前据47条日志外推12.7–14.8小时漏计了rank1；文件mtime证明暂停前实际已有 **89条完整输出**。按全rank输出修正的同一工作量代理估计约 **6.72–7.84小时**，旧12.7–14.8估计作废。原始快照保留，更正单列；后续监控将核对全部rank完整文件。

[预算更正证据](runs/R53_native_trace/budget_correction.json)。旧run仍按用户新方案取消，不因更正而续跑；后续仅运行官方关闭TCP的一次完整实际候选推理，并等低负载、现场估计<8小时后自动启动。
