# AGENTS.md

## 通用原则

1. 我们不是一篇安全攻防论文，你有权力进行校验，但是禁止禁止禁止过度防御。
2. 禁止为反复出现的基本不可能发生的 case 写防御。
3. 需要 rubric 的地方不要过度机械化。
4. 每次任务开始先确认项目身份：当前项目根目录必须是
   `/data3/liuyeqiang/YesTrackV2`（2026-11-20 用户授权从 NAS 恢复的独立 A100 工作区；分析任务目录为 `yestrack_diagnosis_20261101`；原 `/data2/user/LocateMOT_GroundJEV` 及旧 LocateMOT 路径仅作来源追踪）。若收到的任务/附件指向
   其它项目（例如 OCD_OVMOT / TrackOCD），先提醒用户“这是 LocateMOT 任务吗”，
   避免把复制错的任务执行到本项目。

## 研究执行原则

1. 先阅读代码 -> 写简短研究计划 -> 开始实现和实验，不要长时间停留在文档规划。
2. 仅做保证数值结果可信所必需的 sanity checks；不要把主要精力用于单元测试
   覆盖率、hash、格式化、CI、异常输入防御等。
3. 维护 `research_log.md`，简洁记录：实验假设、失败现象、原因判断、修改内容、
   结果变化、是否保留。

## Long-running experiment policy

For long training or evaluation jobs, never perform agent-level polling.

Use exactly one blocking shell command to wait for completion. Internal shell
sleep and process checks are allowed, but do not repeatedly return to the model
to run ps, tail, wc, ls, date, or nvidia-smi.

After the blocking command returns:

1. Validate completion and output integrity.
2. If the task failed, identify the first actionable root cause.
3. Apply the smallest justified fix.
5. Run a targeted regression test.
6. Resume from the latest valid checkpoint or unfinished unit.

Never hide failures, skip samples, change metrics, change seeds, weaken
acceptance criteria, or silently alter the experimental protocol.

## GroundJEV resource limits

At most four physical GPUs for all GroundJEV processes combined. Set task-local
CUDA_VISIBLE_DEVICES to the registered GPU list. Never restart the old U2
candidate cache/queue route. Temporary feature caches are bounded to 25 GiB;
raw data and checkpoints are preserved separately. GroundAnything DLM and
OneJev use separate environments. Pilot completion does not complete the
full research goal.


## A100 恢复约定

- 数据集、checkpoint 和大型缓存保持在 NAS；路径表见 `recovery/runtime_paths.json`。
- 官方 YesTrack/TrackEval 和 OneJev 源码、冻结 plans/r58.json、既有实验结果保持原样。
- 历史脚本通过 `recovery/run.py analysis/脚本名.py` 启动以转换旧绝对路径；新实验使用新编号和输出目录。
- 当前可复用环境已验证 YesTrack 基线；R58 GPU 原环境尚未恢复，5 组公开模型权重属于原备份明确暂缓项。
- 不把 oracle 上界写成已实现的方法增益；R58 没有模型通过全部冻结标准。

## Git 提交大小约束

- 用户要求所有后续提交严格小于 100 MB，按 **100,000,000 字节**执行。每次提交前检查暂存快照内普通文件的未压缩总大小及最大单文件，均须低于此上限。
- 推送前复核目标分支大小；数据集、checkpoint 与大型缓存继续留在 NAS。官方子模块属于独立仓库，统计时明确区分主仓库与子模块源码的大小。
