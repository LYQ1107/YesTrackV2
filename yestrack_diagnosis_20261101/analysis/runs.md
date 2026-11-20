# Runs

除显式注明的官方仓库工作目录外，所有命令从 `/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101` 执行。固定 seed=`2025`，完整配置在 `analysis/config.json`。R09 已在物理 GPU 3、4 完成完整复现，HOTA=40.132，第一轮未通过 1.5 HOTA 门槛；第二轮用户已取消该停止条件，按 R13 起的记录继续。论文结果均明确标为外部对照。

## R00：官方源代码

```bash
git clone https://github.com/ggbondrighthere24/YesTrack.git analysis/upstream/YesTrack
git -C analysis/upstream/YesTrack rev-parse HEAD
```

结果：`ed42b8315b28c94dc595d83b0d49bf57002bb281`。模型权重与推理代码未修改。

## R01：初始公开分享页连接检查

```bash
curl --location --max-time 30 --silent --show-error \
  --output analysis/baidu_share_response.html \
  --write-out 'http_status=%{http_code} bytes=%{size_download}\n' \
  'https://pan.baidu.com/s/1nwhcEIQshWk9TnNjhiYMrQ?pwd=z5kt'
```

结果：HTTP 200，16,015 字节，页面标题为“百度网盘 请输入提取码”。这只证明网页可访问，不代表已下载权重。R03 使用发布的提取码继续验证并查看文件列表。

## R02：本地资源、数据完整性和配置检查

```bash
python3 analysis/audit_reproduction.py \
  --config analysis/config.json --output analysis/preflight.json
```

检查内容：固定 commit、官方代码未修改、官方 V2 split、各序列图像/标注/表达式文件数量、全部本地 PEFT adapters 与 YesTrack ZIP、基座存在性、候选 Python 环境版本、推理/评测默认配置。递归文件检索显式包含 gitignored/hidden 文件。只读取文件和软件包元数据，不做 GPU 推理或类别分析。输出和执行状态见 `analysis/preflight.json`。

执行成功。源代码干净；val 为 862 条表达式、2,069 张图像、1,990 个逐帧标签文件；train 为 8,896 条表达式、5,939 张图像、5,172 个标签文件。图像与标签文件数不同，尚未将无文件帧判为缺失或空 GT。检索到 59 个本地 adapter 配置，未发现 `v2bestweight` 或以 Qwen3-VL-2B 为 base 的 adapter；未找到 YesTrack ZIP。已有带 YesTrack 名称的 adapter 指向 OneJev-0.8B。

2026-11-01 为增加显式 `local_qwen3_vl_2b_adapters` 汇总字段，以同一命令重跑一次；原始库存数值不变。

## R03：官方资源提取码和匿名下载可用性

```bash
python3 analysis/probe_release.py \
  --config analysis/config.json --output analysis/release_probe.json
```

按官方链接与提取码访问正常的 `share/verify`、公开分享页和 `share/list`；记录返回码、文件名、大小及正常下载所需字段的存在性。输出和执行状态见 `analysis/release_probe.json`。

执行成功：提取码 `verify_errno=0`；两个目录列表均 `errno=0`，公开文件为 `/Yestrack/yestrack.zip`，大小 178,142,422 字节。列表没有 `dlink`，验证后的分享页没有正常 sharedownload 所需的 `sign` 和 `timestamp`。状态为 `PUBLIC_ARCHIVE_LISTED_ANONYMOUS_DOWNLOAD_UNAVAILABLE`。本次没有取得压缩包、官方 adapter 或官方 tracker 候选。

## R04：论文对照数字

原始来源：[YesTrack arXiv v1，Table 2 / §4.1](https://arxiv.org/html/2609.02318v1)。

| Tracker | HOTA | DetA | AssA |
|---|---:|---:|---:|
| YesTrack-MOT | 43.75 | 37.04 | 52.36 |
| TempRMOT* | 41.78 | 32.69 | 53.75 |

该来源的 Table 4 GT tracks referential Acc=91.15、Prec=74.14、Recall=85.71 属于 **Refer-KITTI V1**，不能填入 V2 的复现对照列。论文主文未给出对应的 V2 GT tracks referential 数字。

## 初轮后续计划（资源恢复前的历史状态）

以下是 R05 前的状态；最终复现结果与停止原因以 R09/R12 为准。

V2 复现、GT tracks referring、A–H 分类、误差分解、四个探针及错误可视化尚未运行。取得官方资源并通过复现门槛后，逐项添加实际执行的完整命令；不以命令模板或未运行的配置充当实验记录。

## R05：扩大检索并使用服务器已存百度网盘登录

用户授权检查其现有网盘登录及必要时二维码登录。磁盘扫描扩大到 data0–data3 的可读文件（权限错误单独保存）；未以其他账号凭据代替用户账号。命令：

```bash
rg --files --hidden --no-ignore /data1/user /data2 /data3 /home/user \
  -g 'adapter_config.json' -g '*v2best*' -g '*[Yy]es[Tt]rack*.zip' \
  -g '*[Yy]es[Tt]rack*.7z' -g '*[Bb]aidu*' -g '*[Bb]yp[yY]*' \
  -g '*netdisk*' -g 'BaiduPCS-Go' -g 'baidupcs-go' -g '*[Bb]aiduPCS*' \
  > analysis/expanded_asset_paths.txt 2> analysis/expanded_asset_search_errors.log
rg --files --hidden --no-ignore /data0 \
  -g 'adapter_config.json' -g '*v2best*' -g '*[Yy]es[Tt]rack*.zip' \
  -g '*[Yy]es[Tt]rack*.7z' \
  > analysis/data0_asset_paths.txt 2> analysis/data0_asset_search_errors.log
rg --files --hidden --no-ignore /data1 /data2 /data3 /home/user \
  -g '*.zip' -g '*.7z' -g '*.rar' -g '*[Yy]es[Tt]rack*' \
  > analysis/archive_and_yestrack_paths.txt 2> analysis/archive_and_yestrack_search_errors.log
/data3/user/TTA-RMOT-assets/bin/BaiduPCS-Go search -r --path=/ yestrack
/data3/user/TTA-RMOT-assets/bin/BaiduPCS-Go meta /Yestrack/yestrack.zip
```

找到了客户端与 `/home/user/.config/BaiduPCS-Go/pcs_config.json` 保存的账号。网页接口返回 errno=-6，但 PCS 搜索成功并找到 `/Yestrack/yestrack.zip`（178,142,422 字节）。不需要重新二维码登录。登录凭据留在现有客户端配置中，任务结果只记录接口状态和所需文件路径。

## R06：下载、完整性检查并解压官方资源

```bash
umask 077
mkdir -p analysis/resources
/data3/user/TTA-RMOT-assets/bin/BaiduPCS-Go download \
  --saveto /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources \
  --mode locate -p 4 --retry 1 /Yestrack/yestrack.zip \
  > analysis/resources_download.log 2>&1
python3 analysis/inspect_release.py --archive analysis/resources/yestrack.zip \
  --extract-to analysis/resources/release --output analysis/release_inventory.json
```

成功；ZIP CRC 全部通过。4,092 个文件，解压总大小 361,534,107 字节。V2 adapter：`analysis/resources/release/yestrack/v2bestweight`；TempRMOT* 候选和 GT/seqmap 同在该 `yestrack/` 目录。发布包不包含单独 YesTrack-MOT 候选组。完整库存见 `release_inventory.json`。

## R07：隔离数据视图与完整候选清点

```bash
python3 analysis/prepare_reproduction.py --config analysis/config.json
```

首次执行暴露带逗号 seqmap 的 CSV 解析问题：只取第一列截断名称。按官方评测入口的 `','.join(row)` 读取规则作最小修复并以同一命令重跑。19 个 CSV 行包含未引用的逗号；修复后 862 个唯一完整名称全部匹配，不删样本、不改发布 GT/seqmap。1,850,576 条候选记录，MOT 帧 1-based、图像 0-based，记录在 `reproduction_inputs.json`。`config.json` 现已指向恢复的官方资源。

## R08：实际运行检查与环境修复

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
  /data2/user/TTA-RMOT-assets/teacher-p1/env/bin/python -u \
  analysis/smoke_runtime.py --config analysis/config.json \
  > analysis/runtime_smoke.log 2>&1
```

首次失败，尚未加载模型：现有环境 Transformers=4.57.6 缺少官方导入的 `Qwen3_5ForConditionalGeneration`。未修改官方源码，改在任务目录建立独立环境。关键版本取自官方 requirements；其 Pillow file:// 本地构建路径不可移植，使用 Pillow=11.3.0。

```bash
/home/user/.local/bin/python3.12 -m venv analysis/.venv-yestrack
analysis/.venv-yestrack/bin/python -m pip install --no-cache-dir \
  -r analysis/requirements-yestrack.txt > analysis/environment_setup.log 2>&1
```

完整复现将使用 `config.json` 中 `reproduction_environment` 指定的独立解释器，保留原有项目环境。

独立环境第一次导入还暴露了缺少 `einops`；按官方 requirements 的 0.8.1 版本补齐后，以相同 seed 重跑了实际两候选检查：

```bash
analysis/.venv-yestrack/bin/python -m pip install --no-cache-dir einops==0.8.1 \
  > analysis/environment_einops_fix.log 2>&1
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
  analysis/.venv-yestrack/bin/python -u analysis/smoke_runtime.py \
  --config analysis/config.json > analysis/runtime_smoke_repaired_v2.log 2>&1
analysis/.venv-yestrack/bin/python -m pip freeze > analysis/environment.lock.txt
analysis/.venv-yestrack/bin/python \
  analysis/upstream/YesTrack/TrackEval/scripts/run_mot_challenge.py --help \
  > analysis/trackeval_import_check.log 2>&1
```

实际运行检查成功：官方 adapter 确认加载，Yes/No token ID 为 9454/2753，两候选 p=0.96875、0.00860595703125，均有限。这里只验证真实图像/权重/官方 forward 可执行，不作为完整复现或研究结果。详情见 `runtime_smoke.json`；最终环境版本见 `environment.lock.txt`。

## R09：TempRMOT* V2 完整论文参数复现

GPU=3,4，seed=2025，所有 862 个官方 seqmap 条目。控制器命令见下；实际子进程从官方仓库目录执行，命令展开如下。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES=3,4 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u -m torch.distributed.run --standalone --nproc_per_node 2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/seeded_run.py --seed 2025 --script /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/refer_llm/llm_eval_from_mot.py -- --model_name /data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct --lora_path /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2bestweight --data_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/dataset_v2 --results_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2best_track_result --mot_input_type results_root --mot_filename predict.txt --mot_frame_start_one 1 --image_frame_start_one 0 --frame_offset 0 --image_size 320 --margin_ratio 0.2 --video_n_frames 4 --re_refer_lower 0.2 --re_refer_thresh 0.8 --stability_enable --stability_window 3 --stability_thresh 0.4 --stability_boost 0.3 --infer_every_n_frames 10 --preprocess_workers 4 --vis_every 0 --output_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/temprmot_star_paper_v2/predictions
CUDA_VISIBLE_DEVICES=3,4 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/temprmot_star_paper_v2/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/temprmot_star_paper_v2/evaluation --split val --offset 0 --min-area 20.0 --classes pedestrian --thresholds 0.4
```

结果：控制器已完成，862 个任务及 1,850,576 条候选输出完整。HOTA=40.132，DetA=30.520，AssA=53.190；HOTA 差 −1.648，未通过门槛。官方入口、权重和推理逻辑未修改；完整官方 seqmap。

## R10：补充检索 YesTrack-MOT 官方候选与实现

用户明确表示没有额外候选，授权继续网上寻找。以公开接口检查官方仓库分支/提交/标签/发布/fork、作者公开仓库、全部 issue/评论与 Hugging Face models/datasets/spaces：

```bash
python3 analysis/search_public_resources.py
rg -n -i 'rfdetr|rf-detr|TrackLLM|YesTrack.MOT|gating|hungarian' \
  analysis/upstream/YesTrack -g '*.py' -g '*.md'
/data3/user/TTA-RMOT-assets/bin/BaiduPCS-Go search -r --path=/ TrackLLM
```

结果：main/commit 各 1，tag/release/fork 均 0；作者公开仓库 5 个；issue 2 个、评论 4 条；HF 三类结果均 0。会议出版页另外找到 9 页补充材料，浏览器来源可读，内容是伪代码/提示词/额外实验，未见候选下载。原始 PDF 的服务器请求返回 HTML；初次 pdftotext 失败，修正检索脚本为如实保存 HTML 和内容类型后重跑成功，不把 HTML 当 PDF。该修复只影响资源检索脚本。实际资产快照见 `public_resource_search.json`，详细检索范围与来源见 `MOT_RESOURCE_SEARCH.md`。没有自行重写 tracker 或联系作者。

R10 补查：GitHub 连接器 GET `/repos/ggbondrighthere24/YesTrack/pulls?state=all&per_page=100` 返回空列表；公开 `/users/ggbondrighthere24/gists?per_page=100` 也为 0。`search_public_resources.py` 已包含这两个接口，快照合并进 `public_resource_search.json`。

## R11：GT tracks 评测输入准备代码

新增 `analysis/prepare_gt_candidates.py`，调用官方 GT 转换器的框解析函数，准备同一官方 referring 入口可读的候选文件，并核对发布 GT 与本地表达式掩码。该脚本要求 TempRMOT* 的完整 `result.json` 通过 1.5 HOTA 门槛才执行准备。目前只做了代码语法检查：

```bash
python3 -m py_compile analysis/prepare_gt_candidates.py analysis/search_public_resources.py
```

通过；尚未运行 GT 候选生成或 GT tracks 模型评测。

等待流长时间无输出后，另做过一次最终产物核对，只检查 `analysis/runs/temprmot_star_paper_v2/result.json` 是否存在；当次文件尚未生成，继续保留原阻塞作业。没有重启推理或调整实验配置。

R09 完成：HOTA=40.13200，DetA=30.52000，AssA=53.19000；论文 HOTA 差=-1.64800，是否通过 1.5 门槛=False。完整结果：`analysis/runs/temprmot_star_paper_v2/result.json`。

## R09 控制器实际启动命令与最终状态

从本任务根目录执行的完整控制器命令（上面的官方子进程命令由其展开）：

```bash
CUDA_VISIBLE_DEVICES=3,4 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
  HF_HUB_DISABLE_PROGRESS_BARS=1 PYTHONUNBUFFERED=1 \
  analysis/.venv-yestrack/bin/python -u analysis/run_stage0_temprmot.py \
  --config analysis/config.json
```

控制器退出码 0，`within_tolerance=false`；时间 7,950.856446 秒。官方汇总 HOTA=40.132 / DetA=30.520 / AssA=53.190，论文 41.78 / 32.69 / 53.75，差值 −1.648 / −2.170 / −0.560。覆盖率校验通过，862 条表达式、1,850,576 条有限概率记录。完整配置与实际子进程命令见 `runs/temprmot_star_paper_v2/commands.json`；原始指标见同目录 `evaluation/tracker/default_t0p40/pedestrian_summary.txt`。执行到用户的停止条件，未启动 GT referring、分类、探针或错误可视化。

## R12：停止后的来源、标注与图像尺寸核对

这是复现诊断，读取既有输出和原始标注；没有新模型推理、阈值扫描或 TrackEval 评测。

```bash
CUDA_VISIBLE_DEVICES='' analysis/.venv-yestrack/bin/python \
  analysis/audit_reproduction_result.py --config analysis/config.json \
  --output analysis/reproduction_diagnosis.json \
  > analysis/reproduction_diagnosis.log 2>&1
```

首次检查在 0019 发现实际尺寸 (1238,374) 与发布 GT (1242,375) 不同而触发断言。最小修改是把该差异完整写入诊断文件、继续核对标注一致性，并用非零退出码 2 保留“尺寸不一致”的结果；没有改变任何数据、指标、阈值或接受条件。以同一命令重跑后退出码 2：0019 全部 1,059 帧均为 1238×374，其他三段与 GT 尺寸一致。按发布 GT 坐标系，全部 491,286 个正例 object-frame 的帧/ID/三位小数框值与本地 V2 标注完全相符，862 条表达式中不一致 0；上游 tracked diff 为空。该结果核实版本与已存在的坐标约定差异，不能量化该差异对 HOTA 的影响。

发布 V2 权重的官方说明推荐 γ≈0.6，而主运行使用论文 γ=0.4；未继续评测其他阈值。详细归因边界与全部停止项见 `REPORT.md`。

## R13：已有结果的精度/召回归因与逐视频 HOTA

seed=2025。CPU；不做新推理或新 TrackEval。论文附加对照数字由第二轮用户给定。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/r13_diagnostics.py
```

## R14：发布推荐 γ=0.6 重评测及固定附表扫描

seed=2025。CPU only。γ 仅在 eval_refer_kitti_mot.py:206、229–255 和 13–30 的结果过滤生效；推理入口无 γ 参数，1183 行原样保存连续分数。只在 0.4/预给定 0.6 之间按授权选择；扫描不用于选基线。预计约 15–30 分钟。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r14_thresholds.py
```

## R15：0019 候选/GT 坐标与 crop 偏移核对

seed=2025。CPU；不做新推理。对各表达式发布框取唯一(frame,id,bbox)，不重复计相同候选；GT 同样去重。使用官方 crop 坐标函数，margin=.2/min_side=8；报告缩放、仅裁剪边界和未裁剪框三种差值。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/r15_coordinates.py
```

R14 完成：γ=.4 HOTA=40.132；预指定 γ=.6 HOTA=40.427。冻结本地 γ=0.6（发布权重推荐值）。扫描结果仅附表，见 R14/result.json。

## R16：生成完整 GT 候选（移除已废止的复现门槛）

seed=2025。CPU；862 条表达式、2,860,484 条 GT 候选记录；所有正例坐标和标签与发布 GT 完全一致。R15 最大 crop 位移 4.1231 像素，按规则不修正坐标。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/prepare_gt_candidates.py
```

## R17：H2：GT tracks + 官方 YesTrack referring

seed=2025。GPU 阶段开始前预计 3.40 小时（保守范围 3–6 小时，低于 8 小时）；依据 R09 的 2.2 小时按完整候选数比例估算。物理 GPU 3、4；资源注册允许，启动前均空闲。同一发布 V2 权重、γ=0.6、TCP=3/.4/.3、TRP=10、video=4、refine=[.2,.8)。分析 wrapper 只记录官方 helper 原样返回的 frame/video 概率，不修改推理值或顺序。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=3,4 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_h2.py
# 官方子进程工作目录：/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
# /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u -m torch.distributed.run --standalone --nproc_per_node 2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/observed_inference.py --seed 2025 --script /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/refer_llm/llm_eval_from_mot.py --trace-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R17_h2/raw_scores -- --model_name /data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct --lora_path /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2bestweight --data_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/dataset_v2 --results_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/gt_candidates_v2/results --mot_input_type results_root --mot_filename predict.txt --mot_frame_start_one 1 --image_frame_start_one 0 --frame_offset 0 --image_size 320 --margin_ratio 0.2 --video_n_frames 4 --re_refer_lower 0.2 --re_refer_thresh 0.8 --stability_enable --stability_window 3 --stability_thresh 0.4 --stability_boost 0.3 --infer_every_n_frames 10 --preprocess_workers 4 --vis_every 0 --output_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R17_h2/predictions
# /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R17_h2/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R17_h2/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R18：表达式多标签与 100 条人工审计样本

seed=2025。先跑关键词规则，再由当前 Codex LLM 逐条语义审核；冻结审核输出可重放。F 仅由同一可见 GT ID 的真值切换得到（跨可见性空档的切换另记 gap）；G 从发布 GT 空集合得到。A 含明确类别约束；H 只标明示群体/数量，不把普通复数一律当作计数。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/build_labels.py --review analysis/labels/llm_review.json
```

## R20：候选保持不变的 referring oracle 与 H3 sanity

seed=2025。CPU；全 862 表达式；候选框/轨迹 ID/帧不变，逐帧 Hungarian 最大 IoU 匹配完整 GT，IoU>=0.5 后按表达式真值赋 oracle 0/1。H3 复制发布 GT 的原始小数框而非推理入口的整数框，仍使用官方 area>=20、统一类别和完整 seqmap。分类别 ΔHOTA 将用官方 HOTA.combine_sequences 替换对应独立表达式结果后精确重聚合。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/prepare_oracles.py
```

## R19：优先校准/TRP 的实际吞吐计时

seed=2025。GPU 阶段启动前预计 5–15 分钟，参考 R09 2.2 小时，计时范围仅 8 条固定表达式/128 帧/827 个 GT 候选；GPU6 注册允许且启动检查空闲。得到吞吐后再估算完整校准和 F 类 TRP 全量缓存，超过8小时则等待用户授权，不以 pilot 代替全量。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/freeze_semantic_review.py
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/plan_probes.py
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/cache_scores.py --plan analysis/plans/R19_timing.json --out analysis/runs/R19_timing --video
```

## R21：分类误差分解与候选保持的 ΔHOTA

seed=2025。从完整官方 TrackEval detailed CSV 调用原生 HOTA.combine_sequences 精确重算；H2 完成后同一命令更新 H2 及 GT tracks Acc/P/R。未按表达式 HOTA 做简单平均；重叠类别收益不可相加。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/decompose.py
```

## R19b：将 frame 与 video 成本分开计时

seed=2025。GPU 阶段启动前预计约 1–3 分钟；R19 同一批827条样本的 frame+video 实测51.7秒，约17.3条/秒。该测量只跑 frame，不重写推理逻辑；用于判断优先校准全量阶段是否超过8小时，不以计时样本替代正式结果。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/cache_scores.py --plan analysis/plans/R19_timing.json --out analysis/runs/R19b_frame_timing
```

## R22-plan：超过8小时 GPU 阶段的冻结预算（尚未启动）

seed=2025。R19实测17.287 GT候选/秒/GPU（含选择性video）；全量2860484行在4GPU点估计11.49小时，保守11.5–16小时。已准备实现和完整计划，等待用户对超过8小时的授权。V1源域158表达式328330行另需约1.3–2小时。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/prepare_v1_plan.py
# 下面命令只有用户明确批准后才执行：
# /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_score_cache.py --plan analysis/plans/calibration_full.json --out analysis/runs/R22_full_scores --gpus 3,4,5,6 --run-number 22 --estimated-hours 13 --video --over8-authorized
```

## R23：成对上下文探针（全部 C/D 表达式）

seed=2025。GPU 阶段开始前预计 1–2 小时；依据 R19b 约39.7条frame样本/秒/GPU（R09完整基线2.2小时）。全部107条 C/D 表达式 + 同视频等量随机A对照（排除C/D，允许B/E共同标签），每表达式均匀随机24帧、全部GT候选；四种输入使用完全相同单位。原crop为官方margin=.2（未截断宽高1.4bbox），1.5/2.5倍指原crop未截断尺寸，margin分别.55/1.25；整帧逐候选画红框，所有输入均缩放320x320，保持视觉token预算一致；相同官方prompt、发布V2权重、γ=.6，比较纯frame-mode，不混入TCP/TRP。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/context_probe.py
```

## R24：V1 完整 GT tracks referring，供校准阈值迁移

seed=2025。GPU 阶段启动前预计 0.7–1.5 小时，参考 R09 2.2小时×328330/1850576×2GPU/1GPU≈0.78小时；低于8小时。完整158表达式、328330候选，V1发布权重、同一TCP/TRP；GPU5启动前余量超过30GiB，保留其他项目进程。V1最优阈值迁移到V2使用各自发布权重，所以效应包含权重校准版本变化，不能单归为数据集变化。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=5 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_v1_calibration.py
# 官方子命令：/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/observed_inference.py --seed 2025 --script /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/refer_llm/llm_eval_from_mot.py --trace-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R24_v1_calibration/raw_scores -- --model_name /data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct --lora_path /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v1bestweight --data_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/dataset_v1 --results_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/gt_candidates_v1/results --mot_input_type results_root --mot_filename predict.txt --mot_frame_start_one 1 --image_frame_start_one 0 --frame_offset 0 --image_size 320 --margin_ratio 0.2 --video_n_frames 4 --re_refer_lower 0.2 --re_refer_thresh 0.8 --stability_enable --stability_window 3 --stability_thresh 0.4 --stability_boost 0.3 --infer_every_n_frames 10 --preprocess_workers 4 --vis_every 0 --output_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R24_v1_calibration/predictions
```

## R22-queue：获批全量阶段的阻塞队列

seed=2025。用户已于本轮明确回复“批准全量运行（推荐，完成全部校准和 TRP 扫描）”。GPU 阶段预计11.5–16小时，点估计11.49小时，预算13小时；先等待R17/R23/R24完成释放同一组GPU。只在此单一阻塞命令内部等待依赖，模型端不轮询进程/日志；不停止其他项目进程。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=3,4,5,6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/queue_full_scores.py
```

## R18-groups：表达式依赖性核对

seed=2025。记录完整规则→LLM冻结审核→标注F/G→抽100条→冻结探针采样的命令链。相同GT成员时序的表达式属于同一标注等价组；只用于界定证据范围，不合并官方评测条目。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/build_labels.py
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/freeze_semantic_review.py
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/build_labels.py --review analysis/labels/llm_review.json
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/label_groups.py
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/plan_probes.py
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/plan_som_and_births.py
```

## R20q：H3 的官方整数框输出对照

seed=2025。CPU；原生推理llm_eval_from_mot.py:1023会int(x/y/w/h)，H2无法绕过。保留主要H3=原始GT框+GT referring≈100，另计算H3_int=完全相同int序列化+GT referring，量化H3−H2里坐标序列化混杂，不改变模型/推理。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/quantization_sanity.py
```

## R30：第二轮全部交付的阻塞完成命令

seed=2025。此单一阻塞owner内部等待完整receipt，不进行模型端进程/日志轮询。先完成H2分类表与错误样例；获批R22全量缓存结束后，R26新生ID批次预计0.5–1.5小时/4GPU（28676条），SoM预计2–4小时/1GPU；每阶段启动前另记预算。校准与TRP共享缓存，失败即明确返回该子命令日志；不跳样本、不更换指标。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/finish_round2.py
```

## R22-priority：同一获批范围内优先交付校准

seed=2025。总范围、权重、crop/prompt/每帧批次和13小时预算不变，仍在用户已批准11.5–16小时阶段内。frame约5–7小时先完成，立即生成全量可靠性图/ECE及源域阈值迁移，再完成TRP所需video。帧概率不会重推，video只读取同一缓存概率。输出原子替换避免CPU校准读到半写入的npz。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
# R22仍为全部862表达式/2860484候选；run_score_cache.py按先frame后video两遍执行。
# frame_complete.json产生后自动在CPU运行analysis/calibration.py，同时继续GPU video缓存。
```

## R30-render：报告与数值图的渲染

seed=2025。纯CPU读取完整JSON/官方TrackEval统计，生成REPORT.md与PNG/PDF。运行中明确保留待完成项，不将草稿标成最终结论。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/render_report.py
```

## R30-replay：完整复现入口（当前不重复启动）

seed=2025。该脚本串起所有已记录的独立命令，保留完整GT/seqmap和seed。脚本含已获用户批准的超过8小时阶段；本次执行由现有阻塞owner完成，不同时重复运行该脚本。图像人工归纳说明保存在error_patterns.md；所有统计数字由JSON/CSV和命令重算。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
bash analysis/reproduce_round2.sh
```

## R32：SIGTERM 中断恢复（不跳过样本）

seed=2025。R23/R24/等待队列均退出143（SIGTERM），日志无模型异常；不宣称已确定发送者。保留R23完整142/214个表达式；R24仅保留预测及全部frame/video观察同时完整的77/158个表达式。截断gzip只恢复完整JSON行，缺少所需观察的表达式完整重推；原文件全部存档。固定seed/权重/参数/指标不变。GPU恢复前预计上下文剩余<2小时，V1剩余<1.5小时；R22已获13小时全量授权。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/recover_interrupted.py --prepare
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/recover_interrupted.py --run
```

## R22-queue：获批全量阶段的阻塞队列

seed=2025。用户已于本轮明确回复“批准全量运行（推荐，完成全部校准和 TRP 扫描）”。GPU 阶段预计11.5–16小时，点估计11.49小时，预算13小时；先等待R17/R23/R24完成释放同一组GPU。只在此单一阻塞命令内部等待依赖，模型端不轮询进程/日志；不停止其他项目进程。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=3,4,5,6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/queue_full_scores.py
```

## R24：V1 完整 GT tracks referring，供校准阈值迁移

seed=2025。GPU 阶段启动前预计 0.7–1.5 小时，参考 R09 2.2小时×328330/1850576×2GPU/1GPU≈0.78小时；低于8小时。完整158表达式、328330候选，V1发布权重、同一TCP/TRP；GPU5启动前余量超过30GiB，保留其他项目进程。V1最优阈值迁移到V2使用各自发布权重，所以效应包含权重校准版本变化，不能单归为数据集变化。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=5 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_v1_calibration.py --resume
# 官方子命令：/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/observed_inference.py --seed 2025 --script /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/refer_llm/llm_eval_from_mot.py --trace-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R24_v1_calibration/raw_scores -- --model_name /data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct --lora_path /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v1bestweight --data_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/dataset_v1 --results_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/gt_candidates_v1/results --mot_input_type results_root --mot_filename predict.txt --mot_frame_start_one 1 --image_frame_start_one 0 --frame_offset 0 --image_size 320 --margin_ratio 0.2 --video_n_frames 4 --re_refer_lower 0.2 --re_refer_thresh 0.8 --stability_enable --stability_window 3 --stability_thresh 0.4 --stability_boost 0.3 --infer_every_n_frames 10 --preprocess_workers 4 --vis_every 0 --output_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R24_v1_calibration/predictions --resume
```

## R23：成对上下文探针（全部 C/D 表达式）

seed=2025。GPU 阶段开始前预计 1–2 小时；依据 R19b 约39.7条frame样本/秒/GPU（R09完整基线2.2小时）。全部107条 C/D 表达式 + 同视频等量随机A对照（排除C/D，允许B/E共同标签），每表达式均匀随机24帧、全部GT候选；四种输入使用完全相同单位。原crop为官方margin=.2（未截断宽高1.4bbox），1.5/2.5倍指原crop未截断尺寸，margin分别.55/1.25；整帧逐候选画红框，所有输入均缩放320x320，保持视觉token预算一致；相同官方prompt、发布V2权重、γ=.6，比较纯frame-mode，不混入TCP/TRP。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/context_probe.py --resume
```

## R33：对话中断后的单命令阻塞接续

seed=2025。对话中断后原V8 exec cell已不存在，但H2、完成owner和R32恢复子进程仍活着。只附着等待已有完整receipt，不重新启动推理。文件等待和存活检查全部在本命令内部执行；不会在模型端反复调用ps/tail/nvidia-smi。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/wait_round2.py
```

## R33-next：每次阻塞等待一个实际完成事件

seed=2025。额外等待会话收到SIGTERM，既有实验owner和子进程持续运行。减少同时占用的exec会话；每次阻塞到实际完成事件后退出释放会话，然后才进行校验或分析。等待期间不新开exec shell；实验不重启。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/wait_round2.py --next
```

## R33：对话中断后的单命令阻塞接续

seed=2025。对话中断后原V8 exec cell已不存在，但H2、完成owner和R32恢复子进程仍活着。只附着等待已有完整receipt，不重新启动推理。文件等待和存活检查全部在本命令内部执行；不会在模型端反复调用ps/tail/nvidia-smi。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/wait_round2.py
```

## R34：H2 工具会话中断后的独立进程恢复

seed=2025。H2保留648/862个预测和全部raw观察同时完整的表达式；其余完整重推，旧数据存档。固定seed/权重/TCP/TRP/γ/指标均不变。GPU阶段预计剩余1–3小时，参考R09 2.2h及已保留候选数；低于8小时。H2及CPU完成owner均通过start_new_session=True脱离工具会话，已运行的R23/R24/R22队列不重复启动。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/recover_h2_detached.py
```

## R30：第二轮全部交付的阻塞完成命令

seed=2025。此单一阻塞owner内部等待完整receipt，不进行模型端进程/日志轮询。先完成H2分类表与错误样例；获批R22全量缓存结束后，R26新生ID批次预计0.5–1.5小时/4GPU（28676条），SoM预计2–4小时/1GPU；每阶段启动前另记预算。校准与TRP共享缓存，失败即明确返回该子命令日志；不跳样本、不更换指标。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/finish_round2.py
```

## R17：H2：GT tracks + 官方 YesTrack referring

seed=2025。GPU 阶段开始前预计 3.40 小时（保守范围 3–6 小时，低于 8 小时）；依据 R09 的 2.2 小时按完整候选数比例估算。物理 GPU 3、4；资源注册允许，启动前均空闲。同一发布 V2 权重、γ=0.6、TCP=3/.4/.3、TRP=10、video=4、refine=[.2,.8)。分析 wrapper 只记录官方 helper 原样返回的 frame/video 概率，不修改推理值或顺序。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=3,4 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_h2.py --resume
# 官方子进程工作目录：/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
# /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u -m torch.distributed.run --standalone --nproc_per_node 2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/observed_inference.py --seed 2025 --script /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/refer_llm/llm_eval_from_mot.py --trace-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R17_h2/raw_scores -- --model_name /data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct --lora_path /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2bestweight --data_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/dataset_v2 --results_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/gt_candidates_v2/results --mot_input_type results_root --mot_filename predict.txt --mot_frame_start_one 1 --image_frame_start_one 0 --frame_offset 0 --image_size 320 --margin_ratio 0.2 --video_n_frames 4 --re_refer_lower 0.2 --re_refer_thresh 0.8 --stability_enable --stability_window 3 --stability_thresh 0.4 --stability_boost 0.3 --infer_every_n_frames 10 --preprocess_workers 4 --vis_every 0 --output_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R17_h2/predictions --resume
# /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R17_h2/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R17_h2/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R33：对话中断后的单命令阻塞接续

seed=2025。对话中断后原V8 exec cell已不存在，但H2、完成owner和R32恢复子进程仍活着。只附着等待已有完整receipt，不重新启动推理。文件等待和存活检查全部在本命令内部执行；不会在模型端反复调用ps/tail/nvidia-smi。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/wait_round2.py
```

## R23-analysis：上下文收益与 A 对照的差值

seed=2025。C按全部A对照比较，D使用同视频0011的A对照；分列C_scene/C_viewpoint。依赖于同GT成员序列的回译表达不当作独立统计重复，不虚报显著性。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/analyze_context.py
```

## R25：Set-of-Mark 联合选择的小样本探针

seed=2025。GPU阶段启动前预计2–4小时（参考R09 2.2小时及R19吞吐，计划仅1704帧左右）；发布V2 LoRA与二分类使用完全相同权重，不增加训练/示例。D全21表达式；G全视频空表达式为0，以100条表达式的空GT帧作为另列对照。比较原crop二分类、同一整帧SoM图上的独立二分类、SoM联合单选+none。Qwen的10/11等为多token，故用完整选项串+换行的teacher-forced log概率之和再softmax，不错误地只读共享首token；不做长度归一化。SoM整帧保留原分辨率，二分类整帧控制使用完全相同图；联合单选对多目标帧有召回上限，分开报告。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/som_probe.py --pilot
```

## R25-pilot：单token/多token选项真实前向检查

seed=2025。GPU阶段启动前预计3–5分钟，依据R19加载/前向时间；原计划中各取一个N≤9和N≥10帧，完全相同输入。保存的两个真实帧结果供正式阶段复用，pilot不标为完整1704帧实验。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/som_probe.py --pilot
```

## R35：先冻结 V1 阈值/精炼区间最优，并校验原生重放

seed=2025。纯CPU；完整158表达式328330个GT候选。γ=.1:.1:.9、pl∈{.2,.3,.4}、ph∈{.6,.7,.8}，按源V1 micro-F1选择；目标V2全量校准尚未产生，用此冻结源配置作迁移。原始TCP/TRP10区间必须逐值重放原生分数，最大差阈值1e-12。后续R27复用本源网格，不为选择源配置查看V2网格。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/calibration_source.py
```

## R36：离线重放第6位舍入差异的定向修复

seed=2025。R35首次CPU回放在0005__black-cars-in-the-left失败：最大差1e-6，未放宽1e-12验收标准。原生入口以f-string写6位小数，np.round在二进制临界值上不同；分析脚本改为完全相同的Python格式化。不改官方推理或分数，只修复离线序列化。先验证触发样本，再重跑完整158表达式源网格。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/diagnose_replay_rounding.py
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/calibration_source.py
```

## R35：先冻结 V1 阈值/精炼区间最优，并校验原生重放

seed=2025。纯CPU；完整158表达式328330个GT候选。γ=.1:.1:.9、pl∈{.2,.3,.4}、ph∈{.6,.7,.8}，按源V1 micro-F1选择；目标V2全量校准尚未产生，用此冻结源配置作迁移。原始TCP/TRP10区间必须逐值重放原生分数，最大差阈值1e-12。后续R27复用本源网格，不为选择源配置查看V2网格。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/calibration_source.py
```

## R37：空GT帧的候选保持 oracle（与G全空表达式分开）

seed=2025。CPU；G全视频空表达式为0，不造新语言样本。只在真实表达式的GT集合为空的帧把全部候选score置0，其余帧、所有框/ID/种子/γ/TrackEval协议保持原样。全862表达式重算，量化时变无目标帧的实际HOTA空间；与F类收益重叠，不能相加。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/empty_frame_oracle.py
```

## R38：真实空GT帧的30个FP补充样例

seed=2025。CPU；原G全空表达式类别仍为0。另从本地TempRMOT*基线的空GT帧误报中抽30个不同(expression,track)组，再组内随机帧，seed2025。保留独立目录/索引，不与主GT候选错误样例混用。GT为空时目标检测FN总体不存在，补充集FN记0。p为实际final输出。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/empty_frame_examples.py
```

## R39：V1最优γ迁移到实际Temp候选的V2 HOTA

seed=2025。CPU读取已有完整评测；源R35选择(.4,.2,.8)，没有根据V2网格选择。区间未变且γ只在评测生效，因此R14的γ=.4结果即精确迁移结果，无需新推理。以冻结本地γ=.6为对照，所有其他主实验仍γ=.6。此源/目标使用各自发布权重，效应包含权重版本变化。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/threshold_transfer_actual.py
```

R17 完成：HOTA=65.232，DetA=48.203，AssA=88.284；耗时 1.400 小时。

## R29：每类别30FP/30FN的完整帧错误可视化

seed=2025。CPU；GT候选+官方H2 referring，以隔离跟踪漏检。seed2025，优先不同(expression,track)错误组，组内随机选帧；不足时从剩余错误帧补足。图中 p_final 是含video/TCP/TRP的实际输出，另标最近一次frame模式原始概率和实际判别帧；不混淆两者。G没有全视频空表达式，无法抽造30FP/30FN；实际数量如实记录。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/error_examples.py
```

## R22：GT frame/video 全量概率缓存

seed=2025。GPU 阶段开始前预计 13 小时；R09 为2.2小时，另依据 R19/R19b 实测吞吐。物理 GPU=3,4,5,6；全量 862 表达式、2860484 候选。使用官方 crop、prompt、模型与 forward helper，保持每帧原批次；只缓存分数供分析，未改官方控制器。多GPU按完整表达式原子领取任务，以免共享GPU成为固定分片的长尾；每帧批次/权重/种子不变，完整任务归属写入各rank receipt。用户已显式批准超过8小时。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=3,4,5,6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_score_cache.py --plan analysis/plans/calibration_full.json --out analysis/runs/R22_full_scores --gpus 3,4,5,6 --run-number 22 --estimated-hours 13.0 --video --over8-authorized
```

## R19c：frame/video分两遍执行的真实输入数值回归

seed=2025。GPU阶段启动前预计1–3分钟；复用R19全部827个真实GT样本的frame缓存，只重推344个uncertain视频样本；逐值验证与R19原联合执行完全相等，必要数值检查通过才启动获批全量两遍缓存。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/cache_scores.py --plan /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/plans/R19_timing.json --out /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R19c_split_regression --video --video-only
```

## R40：错误样例汇总JSON类型修复及原完成owner接续

seed=2025。R29已保存图片/index但清单写入因area计数为numpy.int64而失败。只将清单计数转Python int；定向严格JSON回归通过后重做未完成R29汇总单元，跳过已有完整H2/上下文/分解结果。R22独立全量GPU owner继续，绝不重启；新完成owner只等其receipt。/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/finish_round2.py --resume-h2-deliverables

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/recover_error_manifest.py
```

## R30：第二轮全部交付的阻塞完成命令

seed=2025。此单一阻塞owner内部等待完整receipt，不进行模型端进程/日志轮询。先完成H2分类表与错误样例；获批R22全量缓存结束后，R26新生ID批次预计0.5–1.5小时/4GPU（28676条），SoM预计2–4小时/1GPU；每阶段启动前另记预算。校准与TRP共享缓存，失败即明确返回该子命令日志；不跳样本、不更换指标。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/finish_round2.py
```

## R29：每类别30FP/30FN的完整帧错误可视化

seed=2025。CPU；GT候选+官方H2 referring，以隔离跟踪漏检。seed2025，优先不同(expression,track)错误组，组内随机选帧；不足时从剩余错误帧补足。图中 p_final 是含video/TCP/TRP的实际输出，另标最近一次frame模式原始概率和实际判别帧；不混淆两者。G没有全视频空表达式，无法抽造30FP/30FN；实际数量如实记录。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/error_examples.py
```

## R31：原生推理中TCP/复用分数的阈值越界诊断

seed=2025。只分析实际H2原始观察与最终分数，不修改TCP/TRP，不做新推理。统计无新模型调用但分数由γ下升至γ上的次数，及其中真实FP。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/heuristic_diagnostics.py
```

## R41：实际错误图复核、历史加分归因及报告更新

seed=2025。人工语义归纳保存于analysis/error_patterns.md；当前Codex查看A/B/C/D/E/F/H七张overview、G_empty_frame_control overview及代表性全尺寸A FP01/C FP05/E FN02。所有数值来自R29/R31/R38的完整清单或index，非手算替代；404张主图完整，D仅14FN全保存，G无总体。R31:421297FP中86.8544%饱和、58.4820%最近未加分模型判断<gamma，16843次FP在无新调用的复用帧被TCP推过gamma。只作实际原生轨迹归因，不据此声称修改TCP的HOTA收益；官方代码和权重仍未改。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/render_report.py
```

## R42：实际保存FP的TCP逐帧机制核对

seed=2025。CPU读取两个已经保存的H2误例，重放整个表达式且逐值验证原生6位输出，再展示对应ID最后15个可见帧的实际分数/原始判别。只解释观测到的历史加分，不改TCP/TRP或模型，不运行新推理，不估算移除启发式的HOTA。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/trace_tcp_examples.py
```

## R43：长等待连接接续（不重启实验）

seed=2025。V8 cell259结束但未返回新receipt；该次wrapper未打印最终exit_code，连接结束原因未确认。只读验证delivered仍为context/V1/H2/error_images/split_regression，R30无failure/result，尚无R22 frame_complete。既有实验owner与权重/分片均不重启，仅重新执行阻塞receipt等待；新wrapper明确打印exit_code，避免无输出退出。原全量超过8h授权继续有效。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/wait_round2.py --next
```

## R44：等待连接SIGTERM的记录与自动重连

seed=2025。第二次等待cell267明确返回143(SIGTERM)，没有模型异常。结束后一次性核对：H2已正常结束，R22 queue与R30完成owner均S态，旧receipt waiter残留为0。实际GPU进程继续。只给CPU等待器增加连接级SIGTERM日志；V8 wrapper仅在143时重新附着同一receipt等待，不重新启动模型/候选/缓存。所有连接PID/时间/实际signal存R44_wait_connections，不隐藏失败，不以重连伪造完成。其他非0退出返回根因处理。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/wait_round2.py --next
```

## R27：全量 frame-mode 校准、ECE 与 V1→V2 阈值迁移

seed=2025。CPU；V2全部GT候选原始frame概率，15个等宽概率箱，报告ECE/Brier；不使用TCP后分数代替frame概率。实际发布权重负样本保留率r未知，训练CLI默认.5不是该checkpoint的训练记录，不估计、不执行先验修正。V1用V1发布权重的完整158表达式；V2用V2发布权重；此迁移包含权重版本变化且三个视频重叠，不是独立新视频泛化。用官方原始观察值精确重放TCP/TRP10。γ=.1:.1:.9，pl∈{.2,.3,.4}、ph∈{.6,.7,.8}；区间均在已执行video范围内，仅收窄，无缺失video推断。按V1 micro referential F1选一次配置，再在V2评估；V2网格最优仅作为诊断对照，绝不改变冻结γ=.6基线。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/calibration.py
```

## R45：全量原始frame判别及分序列校准

seed=2025。CPU读取完成的2860484条frame概率，固定主基线gamma=.6，给出总体/类别P/R/F1和分序列ECE。与H2最终输出的差异同时包含video/TCP/TRP，属于描述性联合对照，不能单独当作移除某一启发式的因果收益。不改原生逻辑，不跑新推理，不改变基线，不选择阈值。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/frame_score_stats.py
```

## R26：GT frame/video 全量概率缓存

seed=2025。GPU 阶段开始前预计 1 小时；R09 为2.2小时，另依据 R19/R19b 实测吞吐。物理 GPU=3,4,5,6；全量 532 表达式、28676 候选。使用官方 crop、prompt、模型与 forward helper，保持每帧原批次；只缓存分数供分析，未改官方控制器。多GPU按完整表达式原子领取任务，以免共享GPU成为固定分片的长尾；每帧批次/权重/种子不变，完整任务归属写入各rank receipt。估计低于8小时。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=3,4,5,6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_score_cache.py --plan analysis/plans/trp_births.json --out analysis/runs/R26_birth_scores --gpus 3,4,5,6 --run-number 26 --estimated-hours 1.0 --video
```

## R46：类别正例率及同序列A对照的条件错误率

seed=2025。CPU；P/F1受正例率影响，补充TPR/FPR/均衡准确率，避免把低基率直接归因比较/关系推理。D全21条只出现在0011；A对照直接沿用R23冻结的0011中51条A表达式，未按结果重抽。两组使用该序列全部可见GT候选帧；主γ=.6不变。类别/GT时序家族不独立，不声明显著性或架构因果。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/class_base_rates.py
```

## R28：F 类全量 TRP Δ=1/5/10/20 与切换窗口

seed=2025。CPU重放全532条F表达式、2150942个可见GT候选；所有δ共用同一官方helper分数、γ=.6及TCP=3/.4/.3。复用分数的中间帧仍按官方逻辑再执行TCP，绝不简化为恒定输出。新ID立即判别，使用单独的原始newborn批次缓存。δ10须逐样本与原生H2输出完全一致后才报告。±5窗口只定位gap=1的精确真值切换，跨可见性空档另记，不伪造切换时刻。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/trp_probe.py
```

## R25：Set-of-Mark 联合选择的小样本探针

seed=2025。GPU阶段启动前预计2–4小时（参考R09 2.2小时及R19吞吐，计划仅1704帧左右）；发布V2 LoRA与二分类使用完全相同权重，不增加训练/示例。D全21表达式；G全视频空表达式为0，以100条表达式的空GT帧作为另列对照。比较原crop二分类、同一整帧SoM图上的独立二分类、SoM联合单选+none。Qwen的10/11等为多token，故用完整选项串+换行的teacher-forced log概率之和再softmax，不错误地只读共享首token；不做长度归一化。SoM整帧保留原分辨率，二分类整帧控制使用完全相同图；联合单选对多目标帧有召回上限，分开报告。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/som_probe.py
```

## R25-analysis：Set-of-Mark 统计与空帧误报率

seed=2025。同一γ=.6为主表；联合argmax另列；D单/多目标分开。无目标候选正类F1无定义时保留null，另报告none检测F1及空帧误报率。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/analyze_som.py
```

## R47-launch：随机编号配对对照的预算、输入核对与独立owner

seed=2025。新GPU阶段启动前预计1–2小时/单GPU6，依据原完全相同1704帧实际3373.536秒；小于8小时。R25发现D阳性目标100%为编号1，always-first F1=.71264超过联合.50456，需消除实际排序混杂。相同21D/100空帧表达式、相同1704帧和gamma=.6；只随机编号，不调模型/阈值/采样。crop分数按GT ID原样复用，重新计算相同随机标号整帧的独立/联合分数。/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/som_probe.py --shuffle-candidates --out analysis/runs/R47_shuffled_som

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/launch_shuffled_som.py
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/wait_round2.py --next --shuffle
```

## R47：Set-of-Mark 固定seed随机编号对照

seed=2025。GPU阶段开始前预计1–2小时，单GPU6；参考原同1704帧阶段实际3373.536秒及R09 2.2小时。每(sequence,frame)用seed=2025+100000*int(sequence)+frame固定随机排列，编号不依赖表达式或GT referring。原crop输入不变，其概率按GT ID重排复用R25；同一随机标号整帧上的独立二分类和联合选择均重新前向。发布V2 LoRA与二分类使用完全相同权重，不增加训练/示例。D全21表达式；G全视频空表达式为0，以100条表达式的空GT帧作为另列对照。比较原crop二分类、同一整帧SoM图上的独立二分类、SoM联合单选+none。Qwen的10/11等为多token，故用完整选项串+换行的teacher-forced log概率之和再softmax，不错误地只读共享首token；不做长度归一化。SoM整帧保留原分辨率，二分类整帧控制使用完全相同图；联合单选对多目标帧有召回上限，分开报告。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/som_probe.py --shuffle-candidates --out analysis/runs/R47_shuffled_som
```

## R47-analysis：Set-of-Mark 统计与空帧误报率

seed=2025。同一γ=.6为主表；联合argmax另列；D单/多目标分开。无目标候选正类F1无定义时保留null，另报告none检测F1及空帧误报率。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/analyze_som.py --out analysis/runs/R47_shuffled_som --run-number 47-analysis
```

## R48：最终交付核对：覆盖、同输入对照、人工审核表及官方源码

seed=2025。CPU；只做结果可信和交付完整所需核对，不重跑已通过的GPU推理/全量TrackEval。原生重放须差0；SoM softmax归一化按FP32累计误差检查1e-6，二者为不同条件。随机编号前后按GT ID逐值核对crop概率/标签和候选集合，不能只比较汇总F1。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/final_validation.py
```

## R49：预注册：自锁曲线与原生逐值重放门槛

seed=2025。2026-11-02；在任何第三轮结果前冻结 analysis/plans/round3.json。先对全部862表达式/2860484条GT记录执行V0与R17逐值核对；沿用R36原生Python六位格式化，最大差须≤1e-12，且原生HOTA=65.232，否则停止。R49全F类gap=1真→假事件、offset0..15，事件加权，缺失可见帧不插值；视频均值仅对原路由命中项并报告覆盖。延迟右删失、锁存区间及q辅助对照定义均已冻结。CPU，不做新推理。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3.py --stage gate
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3.py --stage R49
```

## R50：预注册：全部时序变体、四序列LOSO及官方TrackEval

seed=2025。变体集合冻结，完成后不增删：V0原生TCP3/.4/.3+TRP10；V1无TCP/TRP10；V2仅历史队列改读最近新鲜原始q（TRP间保持q），最终输出TRP缓存与加分基数不改；V3每帧+video/无TCP；V4_fixed、V4_LOSO、V5_fixed、V5_LOSO。q固定为frame p∈[.2,.8)时取video，否则frame。V4温度固定1，仅拟合偏置、共享p_stay、后验阈值3标量；V5无校准、仅拟合后两项。固定版b0/stay.95/阈值.5，因此V4_fixed与V5_fixed预先声明相同（不是结果后合并）。新ID先验遵用户要求取训练三序列正例率，不是额外可调超参。偏置训练BCE，stay网格{.5,.75,.9,.95,.98,.99,.995}，阈值网格{.1,.2,.3,.4,.5,.6,.7,.8,.9}，只按训练三序列pooled micro-F1选参；并列按更小stay、阈值离.5更近、阈值更小。四折未见序列输出合并后用官方TrackEval，γ=.6、min-area20、整数框不变，HMM后验按各自τ写成0/1决策。每版报告全部指定指标及A-H子集相对V0的ΔHOTA；恢复空间分母固定32.488。r未知不估计。完整定义见冻结JSON。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3.py --stage R50
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3.py --stage report
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3.py --stage all
```

## R51：预注册：实际候选缓存的条件触发和CPU耗时估算

seed=2025。只做CPU算术，不启动GPU。若任一预注册固定/LOSO变体相对V0≥2HOTA，按R22全量frame+selective-video实测总壁钟与实际Temp候选行数比例估时，明确假设相同video命中率及4GPU可用性。无论估算是否超过8小时，都遵用户R51规定等待新的显式GPU授权；超过8小时明确询问。未达+2则不运行GPU阶段。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3.py --stage report
```

## R50-launch：CPU独立owner与单条阻塞等待命令

seed=2025。不启用GPU。独立owner顺序执行已预注册gate/R49/R50/report；等待脚本在shell进程内检查完成receipt和进程，每个阶段仅打印一次完成通知，不做agent级轮询。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3_owner.py launch
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3_owner.py wait
```

## R50-report-resume：报告格式化错误的最小修复与定向续跑

seed=2025。首轮CPU owner在247.407秒内完成全部V0-V5预测、四折训练和TrackEval；报告模板中的内嵌f-string未转义字面量p，导致UnboundLocalError。仅把模板中的{p:.6f}转为字面量，未改任何实验/参数/度量；保留失败receipt和R49_R50_failure.json，直接从完整R49/R50结果生成报告，不重跑实验。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3.py --stage report
```

## R50-validation：CPU交付完整性与LOSO数值核对

seed=2025。必要的数值核对已通过：全部8个预注册行均2860484记录，官方summary与原生combined HOTA一致到三位；HMM全部后验与写入0/1判定逐值一致；V4_fixed/V5_fixed完全相同；四折整视频留出、先验仅来自训练折、拟合标量≤3。空帧分母237085，精确真→假后窗口分母3529；r仍未知。官方tracked diff为空，commit保持ed42b8315b28c94dc595d83b0d49bf57002bb281。只修复报告模板错误；原失败receipt保留，CPU最终完成见R50_validation/result.json与round3_state.json。R51只估时8.406861h，GPU未启动。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3.py --stage report
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3_validate.py
```

## R52：用户续补预注册：Δ10观测预算对齐、LOSO稳健性、机制汇总

seed=2025。先于任何新结果冻结analysis/plans/round3_budget.json，不增删原R50变体。新增用户明确请求的V4_D10_fixed和V4_D10_LOSO；只读原生R17实际frame/video观测，Delta10非空帧计数及新ID立即验证与V0完全相同，中间帧仅状态转移，不重复发射、不读R22。固定b0/T1/stay.95/τ.5；LOSO重新在每折训练三序列上用实际观测BCE拟合b，再以全部训练候选帧micro-F1从原R50网格选stay/τ，至多3标量；先验是训练对象帧正例率。按用户新增规则：只有稀疏HMM>=+2才估算原生Delta10实际Temp带trace推理，估计<8h直接执行；否则不启GPU、再问全帧缓存授权。CPU先全部完成。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3_budget.py
```

## R52-validation：预算对齐CPU检查完成及完整中间帧核对

seed=2025。Δ10固定HMM68.2334376(+3.0014508)，LOSO69.4820828(+4.2500960)。LOSO四序列增量+4.4128/+6.1946/+1.5672/+3.6186；固定版0013为-1.1161。原R50预算及R49机制已并入REPORT_round3.md。真实frame观测322347/video95685，全部新观测重放V0差0；两版本各2538137条未观测行与纯状态预测逐值差0，未读取R22跳过帧。全部CPU补查通过，触发用户新GPU条件分支。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3_budget.py > analysis/runs/R52_budget_cpu.log 2>&1
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/round3_budget_validate.py
```

## R53：预注册：实际TempRMOT*仅Δ10原生带trace一次及冻结参数离线重放

seed=2025。GPU阶段开始前预计7.172小时/2GPU(5,7)，低于8小时；参考R09同实际候选实测2.2086小时，按R22共享GPU5最慢阶段吞吐相对正常3GPU均值的3.247倍耗时保守放大，细节写入analysis/plans/round3_actual_native_trace.json。当前5/7各约54GiB空闲、与外部Showo/DCVC共享，GPU3/4/6余量更小；不终止其他用户任务，项目最多占2张。用户本轮已明确授权满足+2且<8h可直接执行，不再次询问。原生推理参数与R09完全相同，观测wrapper原样沿用R17；仅一次Delta10推理，不跑完整逐帧缓存。结果前冻结5个CPU重放版本：Actual_V0/V1/V2/HMM10_fixed/HMM10_LOSO；LOSO直接转移R52对应训练三序列参数和先验，实际候选上不拟合任何参数。新native_V0必须逐值差≤1e-12，否则停；与R09差异单列，所有实际收益以配对的新V0为基准。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES=5,7 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_actual_native_trace.py launch
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_actual_native_trace.py wait
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/actual_temporal_replay.py
```

R53 启动前命令展开（已通过用户条件授权与R52验证）：

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES=5,7 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u -m torch.distributed.run --standalone --nproc_per_node 2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/observed_inference.py --seed 2025 --script /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/refer_llm/llm_eval_from_mot.py --trace-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R53_native_trace/raw_scores -- --model_name /data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct --lora_path /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2bestweight --data_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/dataset_v2 --results_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2best_track_result --mot_input_type results_root --mot_filename predict.txt --mot_frame_start_one 1 --image_frame_start_one 0 --frame_offset 0 --image_size 320 --margin_ratio 0.2 --video_n_frames 4 --re_refer_lower 0.2 --re_refer_thresh 0.8 --stability_enable --stability_window 3 --stability_thresh 0.4 --stability_boost 0.3 --infer_every_n_frames 10 --preprocess_workers 4 --vis_every 0 --output_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R53_native_trace/predictions
```

## R53-budget：实测超过自动执行预算，暂停本任务进程并保留全部进度

seed=2025。初始7.1718h用R22共享卡吞吐参考；当前实际原生运行25.172分钟完成47/862(0005前段)、48363候选行。给初始化扣除宽松120秒后，按总表达式图像帧工作量外推12.691h，按候选行工作量外推14.811h；仅是当前负载的代理估算，后续序列/路由/其他用户负载会变化，非精确上下界。均已超过用户<8h自动执行条件，故SIGSTOP仅本任务owner/torchrun/两worker四个PID，保留内存和已完成预测/trace；没有终止其他用户任务，没有新增GPU推理，没有改变模型/参数/seed，没有宣称部分GPU结果已完成。原单条阻塞等待被操作性中断，未做agent轮询；进程状态T已一次核对。新的SIGCONT继续需用户批准。完整全帧缓存仍未授权且未启动。暂停收据budget_pause.json及pause_validation.json。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/actual_trace_budget_control.py
```

## R54：用户新方案预注册：路由核查与GT候选V1单参数γ-LOSO

seed=2025。在任何新对照结果前冻结analysis/plans/round3_gamma_control.json。原R50集合不变，新增单一V1_gamma_LOSO：只用R50 V1的Delta10/noTCP/固定video缓存，训练3序列pooled语义micro-F1选γ∈{.1,.2,.3,.4,.5,.6,.7,.8,.9}，与R52HMM目标和阈值网格一致；并列取更近.6再更小。每折仅拟合1标量，未用完整val选参。留出序列判定写0/1，官方TrackEval仍传.6、面积20、整数框。对比固定γ的V1与R52稀疏LOSOHMM。代码已核查video路由在945-949行使用本次frame概率，新ID候选限制在944，TCP在1004-1017行才执行，跳过旧ID不参加video。旧R53按用户指示终止，原4PID均已退出、显存释放，保留89个完整输出和旧trace，不续跑。旧预算将纠正rank0-only日志漏计，不把89条当完整结果。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/stop_superseded_trace.py
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/gamma_loso_control.py
```

## R55：预注册：低负载自动准入、官方实际候选noTCP推理与两种HMM

seed=2025。在任何新R54/R55结果前冻结analysis/plans/round3_actual_notcp.json。旧R53取消不续跑；实际V0直接R14 HOTA40.427不重推。新native只删除R09的--stability_enable，其余科学参数保持，复用原样observed_inference记录frame/video；官方γ.6评测即实际V1。新trace的V1逐值重放须按R36格式差≤1e-12，否则停。结果前冻结三版本：nativeV1、HMM固定b0/T1/stay.95/τ.5、HMM实际候选四序列LOSO。后者只在其余三序列的R20固定候选匹配GT上拟合b/stay/τ≤3标量，网格及micro-F1目标与R52一致；未在完整val选参。中间帧仅状态转移。准入只在shell owner内部采样GPU，连续3次30秒间隔、2卡各空闲≥24GiB、总项目卡数≤4且预估<8h才加载模型；以R09 2.209h乘1.25余量和繁忙卡foreign context竞争系数估时；启动前另写实际卡号、现场负载、估算和展开命令。全部rank完整输出统计进度，修正旧rank0-only预算错误。用户已授权条件满足后自动启动，不再问。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_notcp_when_ready.py launch
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/run_notcp_when_ready.py wait
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/notcp_actual_replay.py
```

## R54-complete：CPU阈值对照结果及旧预算统计修正

seed=2025。V1单参数γ-LOSO HOTA68.0349027；γ各折0005=.6/0011=.6/0013=.6/0019=.7；V1固定68.7389948，R52HMM69.4820828。γ控制-0.7040920，HMM比γ控制+1.4471801，原始gap.7430880；不把它泛化为独立滤波显著性，0013仍弱。video路由依据本次freshframe，在TCP前，完整代码行号已写REPORT。旧R53暂停时89个全rank完整输出，原只数rank0的47导致预算高估；corrected6.718–7.837h，原12.7–14.8h作废，原始错误快照保留。旧run已取消不续跑、显存释放，两个gzip trace均有效闭合归档。R55待持续低负载现场估时<8h自动启动。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/gamma_loso_control.py > analysis/runs/R54_gamma_control.log 2>&1
```

## R55-start：低负载准入通过；GPU启动前估算与完整命令

seed=2025。加载模型前连续3次、间隔30s资源准入通过；预计5.521h<8，物理GPU=4,6。现场selected=[{"index": 4, "uuid": "GPU-44f62835-4095-23ec-d3dd-5af16a00705c", "free_MiB": 70017, "utilization": 23, "existing_contexts": 4}, {"index": 6, "uuid": "GPU-883c8be3-25b0-3d19-6fa8-4c2e335e67d2", "free_MiB": 64971, "utilization": 92, "existing_contexts": 1}]。按R09实际2.209h乘1.25余量和(1+繁忙卡既有context数1)估算。用户已授权满足条件自动启动，不再问。官方模型科学参数与R09差异经列表比较仅有--stability_enable删除；wrapper仍为R17同一文件。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
# 原生入口工作目录：/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES=4,6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u -m torch.distributed.run --standalone --nproc_per_node 2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/observed_inference.py --seed 2025 --script /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/refer_llm/llm_eval_from_mot.py --trace-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_native/raw_scores -- --model_name /data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct --lora_path /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2bestweight --data_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/dataset_v2 --results_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2best_track_result --mot_input_type results_root --mot_filename predict.txt --mot_frame_start_one 1 --image_frame_start_one 0 --frame_offset 0 --image_size 320 --margin_ratio 0.2 --video_n_frames 4 --re_refer_lower 0.2 --re_refer_thresh 0.8 --stability_window 3 --stability_thresh 0.4 --stability_boost 0.3 --infer_every_n_frames 10 --preprocess_workers 4 --vis_every 0 --output_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_native/predictions
```

## R55-recovery：NCCL末尾同步超时；保留完整查询，恢复未完成单元

seed=2025。首个错误为rank0末尾collective等待较慢rank1超过600s，非OOM。已运行2.526h。760个预测文件中752个同时通过完整行数/原R09框几何/观测时间表/video路由/原生V1六位逐值差0核对；其余110个查询完整重跑，不丢样本。原始失败日志与可能缺gzip尾部的trace保存在attempt01，恢复完整JSON前缀仅用于已通过门槛的查询。仅analysis外层将NCCL同步timeout设8h；官方源码、weights、seed、科学参数、三个预注册变体均不改。续跑仍nproc2、官方--resume；新trace单独存attempt02后严格合并。启动前重新连续3次资源准入；剩余估时=R09全量估时×2×剩余最重rank候选行/全量行，并要求已耗时+剩余估时<8h。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/resume_notcp_native.py prepare
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/resume_notcp_native.py launch
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/resume_notcp_native.py wait
```

## R55-recovery-validation：恢复脚本排序修正与定向回归通过

seed=2025。首次CPU prepare在归档和核对后因manifest顺序与官方任务顺序不同触发排序assert；排序仅用于资源预算的rank划分，没有产生推理或指标结果。现按官方712–717行seq/expr排序，保留原始归档并重跑CPU核对通过。752查询原生V1最大差0；8份完整预测缺少完整trace已归档并列入110条重跑单元。额外CPU mock验证同步timeout8h传入原函数、原函数返回值原样返回；官方tracked diff为空。三个预注册变体不变。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/resume_notcp_native.py prepare
```

## R55-resume-start：续跑前资源、预计剩余耗时与展开命令

seed=2025。连续3次30s准入通过；物理GPU=4,6，剩余预计2.764h，含失败前计算的总预计5.290h<8。全量R09参考估时5.521h乘最重剩余rank工作比0.500537；现场selected=[{"index": 4, "uuid": "GPU-44f62835-4095-23ec-d3dd-5af16a00705c", "free_MiB": 81151, "utilization": 0, "existing_contexts": 0}, {"index": 6, "uuid": "GPU-883c8be3-25b0-3d19-6fa8-4c2e335e67d2", "free_MiB": 64971, "utilization": 37, "existing_contexts": 1}]。仅官方--resume和analysis同步超时外层，保持seed2025和全部模型参数；不是新变体。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
# 原生入口工作目录：/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES=4,6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u -m torch.distributed.run --standalone --nproc_per_node 2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/observed_inference_timeout.py --seed 2025 --script /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/refer_llm/llm_eval_from_mot.py --trace-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_native/attempt02/raw_scores -- --model_name /data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct --lora_path /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2bestweight --data_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/dataset_v2 --results_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/v2best_track_result --mot_input_type results_root --mot_filename predict.txt --mot_frame_start_one 1 --image_frame_start_one 0 --frame_offset 0 --image_size 320 --margin_ratio 0.2 --video_n_frames 4 --re_refer_lower 0.2 --re_refer_thresh 0.8 --stability_window 3 --stability_thresh 0.4 --stability_boost 0.3 --infer_every_n_frames 10 --preprocess_workers 4 --vis_every 0 --output_root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_native/predictions --resume
```

## R55-complete：全量实际候选结论、分类汇总和最终核验

seed=2025。862表达式/1850576行；frame239467、video58209；新原生V1六位重放最大差0，三版本缓存对输出差0，官方详细结果均覆盖862条。R14 V0=40.427461892，原生V1=41.211111384(+0.783649491)，固定HMM=41.087281421，LOSOHMM=40.149440485；后两版相对V1分别-0.123829963/-1.061670899，四序列LOSO HMM均低于V1。LOSO每折整视频隔离、3标量、先验仅训练3序列；每版1611109未观测行均只状态转移且误差0。8份重跑完整预测相对失败前原预测最大差0。新GPU原生运行累计5.136628h（首轮2.526356h+恢复2.610272h），未运行全帧缓存。GT单γ对照68.034903 vs HMM69.482083，限冻结网格目标。新增类别表只是既有官方详细结果按固定A–H聚合，不新增变体。报告重绘修正开头GT/实际范围，并防止重绘R54删掉R55；模型/指标/参数不变。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/finalize_round3.py
# 以下为已执行的三次官方TrackEval精确命令；仅重评测时使用，无需GPU
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_actual/Actual_V1_native_noTCP/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_actual/Actual_V1_native_noTCP/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_actual/Actual_HMM10_fixed_noTCP_trace/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_actual/Actual_HMM10_fixed_noTCP_trace/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_actual/Actual_HMM10_LOSO_noTCP_trace/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R55_notcp_actual/Actual_HMM10_LOSO_noTCP_trace/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-inputs：候选字段与R14坐标对齐核查

seed=2025。只读R14和发布候选，全862表达式；本步骤仅核查字段、轨迹元数据及行对齐，不计算任何新HOTA或选择规则阈值。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/audit_r56_inputs.py
```

## R56-preregister：部分oracle与元数据过滤预注册

seed=2025。客户端日期2026-11-04，所有新HOTA/规则结果前冻结analysis/plans/r56.json。R14 gamma=.6、R20匹配均只读。全量字段核查确认9列，第7/8/9列恒1，不能用检测confidence排序。先给TP/匹配但不符合表达式/未匹配三类正候选数，另报语义FN。冻结垃圾oracle、语义oracle（含FN）、固定规则L10/A400、两标量LOSO规则与其仅垃圾命中诊断oracle；不按结果增删。规则36点仅逐视频官方TrackEval缓存，每折只重聚合训练3视频HOTA选L/A，identity和完全相同mask允许复用，完整val仅评OOF，不挑全val最优。全部协议、面积20、gamma.6、seed2025保持。主加法分账先垃圾后语义，同时报单独增益、交互和对称归因；规则实际净收益和仅命中垃圾的oracle收益分别归一到①。不把残差认定为已证明必须看图。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r56_error_oracles.py
```

## R56-eval：GarbageOracle

seed=2025。官方TrackEval；该次完整覆盖862表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/GarbageOracle/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/GarbageOracle/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：SemanticOracle

seed=2025。官方TrackEval；该次完整覆盖862表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/SemanticOracle/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/SemanticOracle/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A400/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A400/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A400/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A400/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A400/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A400/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A400/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A400/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A400/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A400/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A400/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A400/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A900/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A900/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A900/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A900/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A900/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A900/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A900/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A900/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A900/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A900/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A900/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A900/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A1600/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A1600/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A1600/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A1600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A1600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A1600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A1600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A1600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A1600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A1600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A1600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A1600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A3600/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A3600/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A3600/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A3600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A3600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A3600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A3600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A3600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A3600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L1_A3600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A3600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L1_A3600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A0/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A0/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A0/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A0/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A0/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A0/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A0/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A0/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A0/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A0/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A0/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A0/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A400/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A400/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A400/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A400/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A400/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A400/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A400/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A400/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A400/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A400/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A400/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A400/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A900/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A900/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A900/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A900/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A900/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A900/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A900/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A900/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A900/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A900/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A900/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A900/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A1600/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A1600/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A1600/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A1600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A1600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A1600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A1600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A1600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A1600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A1600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A1600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A1600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A3600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A3600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A3600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A3600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A3600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A3600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L5_A3600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A3600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L5_A3600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A0/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A0/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A0/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A0/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A0/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A0/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A0/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A0/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A0/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A0/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A0/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A0/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A400/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A400/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A400/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A400/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A400/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A400/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A400/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A400/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A400/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A400/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A400/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A400/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A900/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A900/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A900/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A900/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A900/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A900/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A900/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A900/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A900/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A900/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A900/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A900/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A1600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A1600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A1600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A1600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A1600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A1600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A1600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A1600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A1600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A3600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A3600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A3600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A3600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A3600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A3600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L10_A3600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A3600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L10_A3600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A0/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A0/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A0/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A0/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A0/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A0/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A0/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A0/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A0/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A0/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A0/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A0/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A400/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A400/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A400/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A400/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A400/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A400/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A400/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A400/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A400/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A400/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A400/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A400/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A900/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A900/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A900/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A900/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A900/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A900/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A900/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A900/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A900/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A900/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A900/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A900/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A1600/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A1600/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A1600/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A1600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A1600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A1600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A1600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A1600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A1600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A1600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A1600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A1600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A3600/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A3600/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A3600/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A3600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A3600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A3600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A3600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A3600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A3600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L20_A3600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A3600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L20_A3600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A0/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A0/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A0/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A0/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A0/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A0/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A0/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A0/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A0/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A0/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A0/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A0/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A400/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A400/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A400/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A400/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A400/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A400/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A400/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A400/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A400/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A900/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A900/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A900/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A900/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A900/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A900/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A900/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A900/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A900/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A900/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A900/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A900/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A1600/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A1600/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A1600/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A1600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A1600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A1600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A1600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A1600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A1600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A1600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A1600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A1600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A3600/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A3600/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A3600/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A3600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A3600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A3600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A3600/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A3600/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A3600/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L40_A3600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A3600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L40_A3600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A0/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A0/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A0/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A0/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A0/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A0/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A0/0013

seed=2025。官方TrackEval；该次完整覆盖207表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A0/0013/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0013.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A0/0013/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A0/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A0/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A0/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A900/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A900/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A900/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A900/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A900/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A900/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A1600/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A1600/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A1600/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A1600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A1600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A1600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A1600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A1600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A1600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A3600/0005

seed=2025。官方TrackEval；该次完整覆盖197表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A3600/0005/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0005.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A3600/0005/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A3600/0011

seed=2025。官方TrackEval；该次完整覆盖228表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A3600/0011/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0011.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A3600/0011/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：grid/L80_A3600/0019

seed=2025。官方TrackEval；该次完整覆盖230表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A3600/0019/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/seqmaps/0019.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/grid/L80_A3600/0019/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：Rule_LOSO

seed=2025。官方TrackEval；该次完整覆盖862表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/Rule_LOSO/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/Rule_LOSO/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-eval：Rule_LOSO_captured_garbage_oracle

seed=2025。官方TrackEval；该次完整覆盖862表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/upstream/YesTrack/eval_refer_kitti_mot.py --refer-root /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/Rule_LOSO_captured_garbage_oracle/predictions --refer-structure nested --gt-folder /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2 --seqmap-file /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/resources/release/yestrack/refer_kitti_motc_gt_v2/seqmaps/val.txt --out-dir /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/runs/R56/Rule_LOSO_captured_garbage_oracle/evaluation --split val --offset 0 --min-area 20 --classes pedestrian --thresholds 0.6
```

## R56-validation：R56完成后核对与报告重绘

seed=2025。CPU；只验证R56新产物，重算每折全部36个训练HOTA并核对选参、检查五个新输出的框/ID和逐行分数；旧R14/R20/R00–R55报告及结果不写入。没有新规则或阈值。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/validate_r56.py
```

## R56-complete：两个部分oracle及LOSO元数据规则的最终结果

seed=2025。R56仅CPU，约14.42min；104次逐视频网格官方TrackEval、40个完全相同mask复用，36点全部保留；另两个部分oracle、OOF规则和垃圾命中诊断全量官方评测均覆盖862表达式。R14 HOTA40.427461892；清垃圾41.802011925(+1.374550032)；纠语义49.490162112(+9.062700219)；R20全oracle51.946196140。交互+1.081483996；先垃圾后语义分账1.374550032/10.144184215；对称归因1.915292030/9.603442217。固定规则40.555147887，LOSO规则40.510873932(净回收①6.068316%)；仅垃圾命中诊断40.589636805，回收①11.798400%，未覆盖垃圾空间1.212375120。逐行核对五个新输出共9252880行，最大score差0，geometry/ID不变；每折36点共144个训练HOTA独立重聚合，选参一致，官方source diff空。之前结果/报告不写入，仅追加runs/research日志。R56报告单独REPORT_R56.md。

```bash
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/validate_r56.py
```


## R58：train 属性概率校准研究（seed=2025；仅 CPU 准备，尚未冻结／推理）

全部新结果位于 `analysis/runs/R58_calibration/`。只读 `config.json` 的 17 个 train 序列；不读取 val 样本或既有 val 概率。先读取官方 model card / 对应 revision 源码与标注，再冻结 `analysis/plans/r58.json`；冻结之前不调用任何模型 forward。原权重、原推理源码与已有结果不修改。

```bash
python3 analysis/r58_discovery.py models
python3 analysis/r58_discovery.py texts
```

以上为模型元数据／官方接口下载与训练表达式文本清点，不是模型推理或实验结果。200 样本试跑后才估算完整 GPU 预算；超过 4 小时须等待用户批准。

R58 用户后续修订：采用取值的一对多二值标签；不从复合表达式推负例；同轨迹静态属性正负变化整轨迹/属性排除；不评多分类 top-label/classwise ECE；每属性正/负各 50 可视化审计；附至少两取值表达式的敏感性子集。全部在冻结前落实。找回原始 KITTI 标注：`/data2/user/reference_envs/kitti_tracking_labels_20261001/data_tracking_label_2.zip`，仅解码 17 个 train 成员。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_data.py > analysis/runs/R58_calibration/data_preparation.log 2>&1
```

此步骤只做 CPU 数据统计；尚无模型推理。V2 ID 与 KITTI ID 不相同，使用逐帧 Hungarian 最大 IoU 一对一匹配（IoU≥0.5），无法匹配的类别/遮挡/截断保留未知。

CPU 准备第一次发现原始 KITTI 匹配率异常低（多数序列为零）：原因是准备脚本将 V2 归一化 x/y 错作中心点。官方 `data/refer_kitti_mot.py:200–210` 明确 x/y 为左上角。只删除该中心转换，保留首轮失败产物于 `R58_calibration/preparation_failures/center_assumption/`，同一命令重跑；尚未冻结计划或做推理，不以失败草稿作结果。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_data.py > analysis/runs/R58_calibration/data_preparation.log 2>&1
```

元数据下载中 d3-mini 最后一个文件出现 TLS EOF；保留原失败原因，沿用已取得的同一 revision，只补缺失元数据，同时补齐 Perplexity 官方 requirements/pyproject（不下载权重）。

```bash
python3 analysis/r58_discovery.py models --repo vllm-sr/d3-mini perplexity-ai/pplx-decider-v1.2
```

冻结前语义审阅：上衣颜色表达式都带具体衣物（T-shirt 或 coat）。标签保留衣物条件，例如 `tshirt:black`，不把“T-shirt 黑色”改写成“任意上衣黑色”；负例只来自独立单属性上衣类型标签已确认的同类衣物。敏感性两取值要求也在同一衣物内计算。保存上一草稿于 `preparation_failures/colour_question_ambiguity/` 后重新准备：

```bash
analysis/.venv-yestrack/bin/python analysis/r58_data.py > analysis/runs/R58_calibration/data_preparation.log 2>&1
```

### R58 简短研究计划与正式冻结

先用 train 的纯单属性表达式构造一对多二值标签，并对齐 KITTI 原始类别/遮挡/截断；排除静态不一致轨迹，保存人工审计样本。冻结 17 条属性/合取题、3 种措辞、两组 Choice 排序、crop 消融、全部样本和模型 revision 后，再用每模型固定 200 样本测吞吐。全部正式温度、阈值、累积系数只在序列 LOSO 训练折拟合；所有置信区间以轨迹聚类 bootstrap1000 次。若预算超过 4 小时，先申请批准，不以试跑代替全量结果。

以下命令生成固定输入图、属性正负审计图，并以独占创建方式冻结全部定义（运行前无任何 R58 模型 forward）：

```bash
analysis/.venv-yestrack/bin/python analysis/r58_protocol.py > analysis/runs/R58_calibration/protocol_freeze.log 2>&1
```

主判定采用用户修订后的二值 ECE：15 等宽、15 等样本量两种都须达到原定门槛；不再评多分类 ECE。多分类问答保留归一化所需的 other 选项，但不建立 other 真值。每个样本始终问相同的全部属性和预注册合取题，不根据已知类别选择题目，以免题目组合泄露标签。Qwen 评分完整选项串，保留全部 token 条件对数似然之和。Perplexity v1.2 公开、可图像本地推理，纳入冻结清单并按官方 dependencies 尝试加载；失败将单列，不替换。

用户继续修订 ECE 判定：15 等样本量二值 ECE 为主、15 等宽交叉核对，分箱判断冲突记部分成立；Brier 增加校准项/分辨项分解，NLL只作诊断。此时仍无任何 R58 模型推理；已完成的初版计划保存在 `protocol_revisions/`，按该用户授权修改后才可启动试跑。GPU preflight 发现驱动570.133.20；Perplexity官方精确依赖torch2.14默认CUDA13，需先检验运行时，不使用不符官方依赖的实现。d3-turbo官网列表确有FP8和INT4，补齐官方卡与revision后，在最终冻结中仅注册显存不足时的官方精度回退。

```bash
python3 analysis/r58_discovery.py models --repo vllm-sr/d3-turbo-FP8 vllm-sr/d3-turbo-INT4
```

### R58 权重准备（不加载、不推理）

/data2 剩余约1GB，原始发布权重下载到 `/home/user/.cache/r58_calibration/models`（该分区剩余约372GB），R58结果目录保留模型链接和revision；不删除任何旧模型/数据。先下载6个确定可用的官方接口模型，Perplexity先核查精确官方运行时兼容性。此阶段无GPU计算，不计作200样本试跑。

```bash
/data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_download.py > analysis/runs/R58_calibration/download.log 2>&1
```

### R58 最终冻结（用户明确修改判定口径；仍未推理）

按最新用户指令删除多分类 ECE 定义，主指标改为二值等样本量15箱 ECE，等宽15箱交叉核对；达标判定冲突记部分成立。Brier校准/分辨/不确定性/分箱残差与NLL为诊断，不参与成立门槛。ECE汇总明确为主表属性宏平均，并另报全属性宏平均和池化结果，避免类别的一对多负例数主导结论。保留先前计划原件；复用完全相同的样本/图/题目，不改任何已有模型结果（此时根本未推理）。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_protocol.py --user-amendment --reuse-prepared-inputs > analysis/runs/R58_calibration/protocol_freeze_final.log 2>&1
```

### R58 Perplexity 精确官方环境尝试（不加载模型）

官方 requirements 固定 torch2.14.0、torchvision0.29.0、transformers5.17.0 等；在 /home 分区创建独立 Python3.12 环境，保留已有 OneJev 和 GroundAnything 环境。安装后只初始化 CUDA 以验证运行条件；若不兼容，保存实际错误并跳过本模型，不用其它版本替代。CUDA13需要驱动>=580，服务器现为570.133.20；来源为 NVIDIA 官方 minor-version compatibility 文档。

```bash
python3 -u analysis/r58_runtime.py > analysis/runs/R58_calibration/perplexity_runtime_owner.log 2>&1
```

### R58 试跑执行（仅冻结的200样本，不启动全量）

6个模型的试跑预计合计约0.5–3小时，属于开始前工程估计；每模型200条主配置，另外5个配置各取同一前10条，实测后逐配置外推所有2065样本。官方INT4的依赖单独装到/home下的overlay，保留原环境。所有GPU阶段由一个阻塞owner依次运行，最多占1张物理GPU，并在启动前检查所有GroundJEV作业的合计4卡限制。owner内部等待权重/资源；不在agent层轮询进程或负载。超过4小时的完整预算不启动全量，先问用户。

```bash
/data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -m pip install --no-cache-dir --no-deps --target /home/user/.cache/r58_calibration/extra310 compressed-tensors==0.17.1 > analysis/runs/R58_calibration/quant_dependency_install.log 2>&1
python3 -m py_compile analysis/r58_gpu.py analysis/r58_owner.py analysis/r58_budget.py analysis/r58_metrics.py
python3 -u analysis/r58_owner.py
```

以上owner只运行pilot并生成budget.json；没有任何隐含全量推理。每个实际GPU命令/显卡/启动前估计还会逐项追加在本文件中。

依赖准备首次失败：既有OneJev环境没有pip（没有改动该环境）；原失败日志保留为 `quant_dependency_install_first_failure.log`。用外部pip的`--python`选择同一解释器并安装到独立target，语义/权重/计划均不变。CPU分析环境没有sklearn，AUROC用等价的Mann–Whitney平均秩公式（SciPy rankdata处理ties），不增加新依赖。

```bash
/home/user/.local/bin/python3.12 -m pip --python /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python install --no-cache-dir --no-deps --target /home/user/.cache/r58_calibration/extra310 compressed-tensors==0.17.1 > analysis/runs/R58_calibration/quant_dependency_install.log 2>&1
```

### R58 开跑前数据实现修正（未产生任何模型分数）

CPU复核发现旧准备实现把“同类/同衣物/同性别确认”也用于GT正例，额外丢失合法正例，与已声明的正例定义不符。立即停止试跑owner；`positive_domain_pause.json`证实`inference_started=false`，分数文件0，子进程0，模型仍在下载。旧样本/统计/审计图全量保留到 `protocol_revisions/before_positive_domain_fix/`，不将旧草稿作正式结果。

最小修正：E_v GT里有可见框即正例，独立同类确认仅用于负例；类别域优先使用同帧独立纯“cars/people”表达式GT，缺失时用原始KITTI对应类别，不能把所有Truck/Tram当作cars负例。衣物和性别条件也只限制负例。判定门槛、题库、模型revision、seed、抽样算法全部保持，重新冻结样本清单后才能启动推理。复用同ID同坐标的已保存输入图，不覆盖旧审计图。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_data.py > analysis/runs/R58_calibration/data_preparation.log 2>&1
analysis/.venv-yestrack/bin/python analysis/r58_protocol.py --implementation-fix-before-inference > analysis/runs/R58_calibration/protocol_freeze_corrected.log 2>&1
```

R58 修正后正式冻结为2144张轨迹帧/540轨迹。主表类别1917张、车辆颜色1628张；样本和正例/负例均按最终JSON审计，旧2065张草稿只留来源追踪。推理仍未开始。执行必要sanity：逐条核对抽样中的可见表达式GT正例没有因域条件被丢弃（静态不一致排除除外），每条源标签的帧键/真假吻合、max8及间隔10、已知Brier/AUROC数值及合成温度恢复。

```bash
analysis/.venv-yestrack/bin/python analysis/validate_r58.py > analysis/runs/R58_calibration/validation_pre_inference.log 2>&1
```

R58 最终依赖核对（仍未模型推理）：只读主环境已满足torch2.10/torchvision.25/transformers5.17/accelerate1.15/safetensors.8；缺少官方einops/OpenCV。按官方d3 requirements把它们与可选官方FLA0.5.2安装到独立overlay（不更改现有环境）；fla-core0.5.2要求torch>=2.7、triton>=3.3，当前torch2.10/triton3.6满足。完整软件版本在试跑前锁定，避免用慢参考路径测预算后再换内核。

```bash
/home/user/.local/bin/python3.12 -m pip --python /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python install --no-cache-dir --no-deps --target /home/user/.cache/r58_calibration/extra310 einops==0.8.1 opencv-python-headless==5.0.0.93 flash-linear-attention==0.5.2 fla-core==0.5.2 > analysis/runs/R58_calibration/runtime_overlay_install.log 2>&1
PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python analysis/r58_environment.py
```

预推理必要检查全部通过：17992次所选源表达式GT正例检查，遗漏0，标签帧/真假错配0；固定max8/间隔10与已知Brier/AUROC/合成T检查通过。最终统计2144张/540轨迹，完整字段见data_statistics.json。

```bash
CUDA_VISIBLE_DEVICES=5 PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python analysis/r58_environment.py > analysis/runs/R58_calibration/environment_lock.log 2>&1
python3 -u analysis/r58_owner.py
```

软件版本已保存environment.lock.json，模型推理尚未开始。/data2空间紧张，未产生分数前创建`R58_calibration/predictions -> /home/user/.cache/r58_calibration/predictions`，所有分数仍由R58目录统一访问、命令复现；仅物理存储改到空间充足的/home，样本/模型/题目/阈值/统计均不变。重新启动同一个阻塞pilot owner，继续等待已在下载的固定revision权重。

R58 200 样本试跑测算（完整明细 `R58_calibration/budget.json`）：

| 模型 | 已测 GPU 阶段(h) | 预计剩余(h) | 完整预计(h) |
|---|---:|---:|---:|
| vllm-sr/d3-mini | download_failed | — | — |
| vllm-sr/d3-flash | download_failed | — | — |
| OmniJev/OneJev1.5-9B | download_failed | — | — |
| Qwen/Qwen3-VL-2B-Instruct | download_failed | — | — |
| Qwen/Qwen3-VL-8B-Instruct | download_failed | — | — |
| vllm-sr/d3-turbo | download_failed | — | — |
| perplexity-ai/pplx-decider-v1.2 | runtime_unavailable | — | — |

总计约 0.000 GPU 阶段小时，其中试跑已用 0.000 小时。所有估计按实际共享负载下吞吐计算，下载与纯CPU准备不计入。未超过4小时，可按用户授权启动同一冻结计划的全量。

### R58 可审阅的准备报告

在完整缓存和预算批准前只生成明确标记未完成的报告，包含最终数据/标签统计、审计位置和模型运行条件，不把200样本试跑用作校准结论。所有P1–P6定义与主/两取值敏感性方案均已冻结，正在实现的CPU脚本仅执行这些定义。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

### R58 首次资源/试跑owner完成后的根因修复

首次六模型下载都在网络客户端构造时失败：`Using SOCKS proxy, but the socksio package is not installed`，各耗时<1秒，没有权重下载、没有模型加载或推理。owner实际只等待Perplexity环境探针；其精确官方torch2.14+cu130已成功安装，但CUDA init真实报驱动过旧（12080），故按用户规则记录runtime_unavailable，不改成torch2.10替代该模型。

缺socksio的下载/owner/budget/旧准备报告完整保留到`preparation_failures/missing_socksio/`。当时0个成功吞吐测量不应视为“预算0小时”；预算脚本改为这种情况下输出unmeasured，不自动放行，属于修正失败状态表达，不改变实验或判定标准。GPU尚未推理，固定2144样本计划不改。最小修复仅补网络依赖，并把overlay用于官方下载客户端。

```bash
/home/user/.local/bin/python3.12 -m pip --python /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python install --no-cache-dir --no-deps --target /home/user/.cache/r58_calibration/extra310 socksio==1.0.0 > analysis/runs/R58_calibration/socksio_install.log 2>&1
```

目标回归检查：用发生错误的同一个官方HfApi客户端读取固定revision元数据并下载小config.json，确认代理依赖真正修复，再续跑未完成权重下载。

```bash
PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python analysis/r58_network_probe.py > analysis/runs/R58_calibration/network_probe.log 2>&1
CUDA_VISIBLE_DEVICES=5 PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python analysis/r58_environment.py > analysis/runs/R58_calibration/environment_lock_after_network_fix.log 2>&1
```

代理依赖目标回归检查已通过：同一官方HF客户端成功读取d3-mini固定revision并下载config.json。软件锁已补入socksio。续跑未完成下载；无权重/模型替换、无样本或判定变化。

```bash
PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_download.py > analysis/runs/R58_calibration/download.log 2>&1
python3 -u analysis/r58_owner.py
```

该owner仍只执行200样本吞吐试跑。输出流转发已完成请求数，避免agent层轮询；完整阶段只支持`--stage full`且必须有预算授权文件，目前未调用。

R58等待由单个阻塞脚本内部完成，进程/已落盘权重/已写入请求数检查留在该脚本中，不在agent层反复ps/tail/wc/nvidia-smi。只观察，不重启或停止实验，不修改冻结定义/分数。替换的是工具输出等待器，原下载与pilot owner继续运行。

```bash
python3 -u analysis/r58_wait.py
```

### R58 大文件下载通道恢复

修复socksio后元数据能取到（mini28/35文件、flash23/37文件），但权重文件未落盘，下载进程线程长期futex/epoll等待。保留`download_xet_stall.log`及Xet partial，停止仅下载进程2003158，不停止pilot owner、不改已缓存模型分数（仍无）。改用官方`HF_HUB_DISABLE_XET=1`普通HTTP通道；非连续Xet partial单独存档，不作为HTTP连续断点复用。模型ID/revision、样本、问题库和判定均不变。

```bash
PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python analysis/r58_http_probe.py > analysis/runs/R58_calibration/network_http_shard_probe.log 2>&1
```

HTTP大文件通道回归已通过：d3-mini固定revision真实safetensors分片返回HTTP206并读取65536字节；不再走卡住的Xet客户端。保留同一模型/权重版本，续跑完成元数据和未完成权重文件，pilot owner等待器继续使用原冻结样本。

```bash
HF_HUB_DISABLE_XET=1 PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_download.py > analysis/runs/R58_calibration/download.log 2>&1
```

R58 下载修复及本地缓存复用（不改变冻结实验）：HF普通HTTP大文件仍有超时；网络范围请求诊断记录在network_transport_benchmark.json。已有原始Qwen2检查点所有官方.metadata均为冻结revision 89644892e4d85e24eaac8bacfd4f463576704203，复用原文件；未加载V2 LoRA。等待下载的owner无GPU子进程，停止该等待进程并按现成检查点优先重启，全部模型/问题/样本/seed不变。

```bash
python3 -m py_compile analysis/r58_reuse_local.py analysis/r58_transport_benchmark.py analysis/r58_owner.py
python3 analysis/r58_reuse_local.py
python3 -u analysis/r58_transport_benchmark.py
python3 -u analysis/r58_owner.py
```

R58 owner首次选择GPU时，读取其它用户PID 923884的cwd触发PermissionError，尚未加载模型；仅修正GPU资源识别对无权读取的其它进程的处理，然后重启同一试跑。

R58 GPU pilot 阶段开始：`Qwen/Qwen3-VL-2B-Instruct`，物理GPU 3；200条main + 其它5配置各10条；预估5–30分钟，27B预估10–40分钟（启动前工程估计，正式预算待实测）。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model Qwen/Qwen3-VL-2B-Instruct --stage pilot
```

R58 传输诊断：固定1MiB官方分片范围请求，HTTP代理11.69秒、直连8.16秒；普通大文件连接多次read timeout。服务器已有aria2，改为同一官方revision的并行HTTP范围下载，每分片16连接，同时最多2分片/模型、2模型；既有连续HTTP前缀复用，完整权重用官方LFS SHA256验证后写官方缓存metadata。仅调整传输，不动模型/样本/指标/随机数；不计GPU预算。旧下载错误日志保留在download_http_sequential.log。

```bash
python3 -m py_compile analysis/r58_fast_download.py
python3 -u analysis/r58_fast_download.py
```

R58 Qwen共享前缀工程修复回归：物理GPU3，启动前预估3–15分钟；对同一试跑250条请求逐值比较，冻结容差仍为0.005，不覆盖任何已存概率。使用TF5.17官方_prepare_position_ids_for_generation及prepare_inputs_for_generation，修正suffix-only输入的M-RoPE切片；模型、完整选项条件似然、批次大小和题库均不变。

```bash
python3 -u analysis/r58_qwen_cache_regression.py
```

R58 cache回归首次命令误用了系统python3，模型在加载前因缺accelerate失败；保留qwen_cache_regression_wrong_interpreter.json，不作为模型不可用结论。纠正为冻结的主环境，不安装/替换依赖：

```bash
PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_qwen_cache_regression.py
```

R58 Qwen共享前缀工程修复回归：物理GPU3，启动前预估3–15分钟；对同一试跑250条请求逐值比较，冻结容差仍为0.005，不覆盖任何已存概率。使用TF5.17官方_prepare_position_ids_for_generation及prepare_inputs_for_generation，修正suffix-only输入的M-RoPE切片；模型、完整选项条件似然、批次大小和题库均不变。

```bash
python3 -u analysis/r58_qwen_cache_regression.py
```

R58 工程回归结果：TF5.17官方位置切片修正后可执行共享缓存，但首条冻结样本与已存完整打分最大概率误差0.0402746，超过原定0.005。因此不放宽容差、不启用该缓存，正式输出继续完整选项条件似然。原250条概率未改。回归失败原件qwen_cache_regression.json保留；Qwen2的已测完整打分吞吐继续有效。
调度器在Qwen2试跑完整落盘后收到SIGTERM（shell退出143，来源未识别）；未完成其它模型，结果不作成功处理。改用独立进程组保存调度器与原日志，从已完成的Qwen2试跑状态继续，预算仍只允许pilot。

```bash
python3 -m py_compile analysis/r58_owner.py analysis/r58_detached_pilot.py
python3 -u analysis/r58_detached_pilot.py
```

R58 官方同一发布者ModelScope传输：metadata在0.2–0.95秒取得，d3-mini 1MiB分片范围请求1.363秒，SHA256与冻结HF manifest相同，64KiB前缀亦与官方HF实取相同。只切换权重字节传输源，每个大文件须ModelScope SHA256/Size等于冻结HF metadata，aria2完成后再校验同一SHA256；源码、配置、tokenizer仍从冻结HF revision获取。旧aria2进程按本任务路径识别后SIGINT保存块进度，未操作其它下载。

```bash
python3 -u analysis/r58_modelscope_probe.py
python3 -m py_compile analysis/r58_fast_download.py
python3 -u analysis/r58_fast_download.py
```

R58 ModelScope首次aria2调用失败：此aria2要求配置路径为普通文件，--conf-path=/dev/null被拒绝（完整日志保留）。改用aria2自带--no-conf=true；所有失败发生在传输启动前，不是模型加载失败，不据此跳过模型。无GPU子进程时停止等待调度器，保留临时下载状态后以相同配置续传。

R58 GPU pilot 阶段开始：`vllm-sr/d3-mini`，物理GPU 3；200条main + 其它5配置各10条；预估5–30分钟，27B预估10–40分钟（启动前工程估计，正式预算待实测）。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model vllm-sr/d3-mini --stage pilot
```

R58 GPU pilot 阶段开始：`vllm-sr/d3-flash`，物理GPU 3；200条main + 其它5配置各10条；预估5–30分钟，27B预估10–40分钟（启动前工程估计，正式预算待实测）。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model vllm-sr/d3-flash --stage pilot
```

R58 GPU pilot 阶段开始：`OmniJev/OneJev1.5-9B`，物理GPU 3；200条main + 其它5配置各10条；预估5–30分钟，27B预估10–40分钟（启动前工程估计，正式预算待实测）。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model OmniJev/OneJev1.5-9B --stage pilot
```

R58 GPU pilot 阶段开始：`Qwen/Qwen3-VL-8B-Instruct`，物理GPU 3；200条main + 其它5配置各10条；预估5–30分钟，27B预估10–40分钟（启动前工程估计，正式预算待实测）。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model Qwen/Qwen3-VL-8B-Instruct --stage pilot
```

R58 CPU报告逻辑核对（尚未计算任何模型校准指标）：修正条目汇总中的逻辑错误，“某一项分箱部分成立”不能覆盖另一项明确不成立；“只有每属性T满足”必须全局T的ECE未满足而每属性T确实满足汇总/主属性ECE；“部分属性”须为非空真子集。保留冻结计划及所有数值门槛，NLL/Brier仍不参与判定。不读取试跑校准质量来作修改。

传输元数据命令的独立可重放实现已补为r58_modelscope_metadata.py；已取得的原始metadata不改，重新下载时先执行该命令，文件字节身份始终由冻结HF revision决定：

```bash
python3 analysis/r58_modelscope_metadata.py
python3 analysis/r58_modelscope_probe.py
python3 -m py_compile analysis/r58_modelscope_metadata.py analysis/r58_report.py
analysis/.venv-yestrack/bin/python - <<'PYTEST'
import sys
sys.path.insert(0,'analysis')
from r58_report import combine_judgments
assert combine_judgments(['成立','成立'])=='成立'
assert combine_judgments(['成立','部分成立'])=='部分成立'
assert combine_judgments(['不成立','部分成立'])=='不成立'
assert combine_judgments(['无法判定','成立'])=='无法判定'
print('frozen criterion combination checks passed')
PYTEST
```

R58 终端监视进程再次以143结束，不能据此认定试跑完成；实际pilot owner使用独立进程组，接回同一owner等待，不重启/重复推理、不改缓存：

```bash
python3 -u analysis/r58_wait.py
```

R58 长任务执行修正：两次前台终端监视收到SIGTERM（信号来源未识别）；独立进程组中的owner与Qwen8推理继续正常，已通过同一阻塞wait接回。新增通用持久launcher，正式阶段获批后运行下列**尚未执行**命令；它先检查原预算授权，再启动原冻结full owner，全部成功pilot模型完整缓存通过后才接CPU分析，失败即保留状态并停止发布。没有增加/删除科学变体。

```bash
# 尚未执行：需要先满足R58 full_budget_approval.json预算门槛
python3 -u analysis/r58_launch.py --stage full
# 若终端监视被宿主终止，只接回同一任务，不重复启动owner
python3 -u analysis/r58_wait.py
```

```bash
python3 -m py_compile analysis/r58_pipeline.py analysis/r58_launch.py analysis/r58_wait.py
```

R58 GPU pilot 阶段开始：`vllm-sr/d3-turbo`，物理GPU 3；200条main + 其它5配置各10条；预估5–30分钟，27B预估10–40分钟（启动前工程估计，正式预算待实测）。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model vllm-sr/d3-turbo --stage pilot
```

R58 200 样本试跑测算（完整明细 `R58_calibration/budget.json`）：

| 模型 | 已测 GPU 阶段(h) | 预计剩余(h) | 完整预计(h) |
|---|---:|---:|---:|
| Qwen/Qwen3-VL-2B-Instruct | 0.217 | 10.808 | 11.025 |
| vllm-sr/d3-mini | 0.066 | 2.587 | 2.652 |
| vllm-sr/d3-flash | 0.076 | 3.305 | 3.381 |
| OmniJev/OneJev1.5-9B | 0.034 | 0.985 | 1.020 |
| Qwen/Qwen3-VL-8B-Instruct | 0.488 | 23.485 | 23.973 |
| vllm-sr/d3-turbo | 0.068 | 2.207 | 2.274 |
| perplexity-ai/pplx-decider-v1.2 | runtime_unavailable | — | — |

总计约 44.325 GPU 阶段小时，其中试跑已用 0.949 小时。所有估计按实际共享负载下吞吐计算，下载与纯CPU准备不计入。超过用户4小时上限，**未启动全量**，等待批准。

R58 试跑完成与正式预算门槛：六模型完整250请求/模型，均为冻结revision，seed=2025；原始YesTrack/qev源码git diff为空。Perplexity官方torch2.14+cu130与驱动12080不兼容，记录runtime_unavailable。当前full授权文件和full_owner_result均不存在。
为保证全量append缓存后仍可重算试跑预算，budget脚本按冻结pilot ID取原200/10条记录；未改变已有概率、吞吐时间或任何预估值。正式阶段状态单列full_inference_started，不改冻结plan。

```bash
python3 -m py_compile analysis/r58_gpu.py analysis/r58_budget.py analysis/r58_report.py analysis/r58_check_pilot.py
python3 analysis/r58_check_pilot.py
python3 analysis/r58_budget.py
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

R58 200 样本试跑测算（完整明细 `R58_calibration/budget.json`）：

| 模型 | 已测 GPU 阶段(h) | 预计剩余(h) | 完整预计(h) |
|---|---:|---:|---:|
| Qwen/Qwen3-VL-2B-Instruct | 0.217 | 10.808 | 11.025 |
| vllm-sr/d3-mini | 0.066 | 2.587 | 2.652 |
| vllm-sr/d3-flash | 0.076 | 3.305 | 3.381 |
| OmniJev/OneJev1.5-9B | 0.034 | 0.985 | 1.020 |
| Qwen/Qwen3-VL-8B-Instruct | 0.488 | 23.485 | 23.973 |
| vllm-sr/d3-turbo | 0.068 | 2.207 | 2.274 |
| perplexity-ai/pplx-decider-v1.2 | runtime_unavailable | — | — |

总计约 44.325 GPU 阶段小时，其中试跑已用 0.949 小时。所有估计按实际共享负载下吞吐计算，下载与纯CPU准备不计入。超过用户4小时上限，**未启动全量**，等待批准。

R58 CPU统计环境记录于CPU_environment.json：Python3.12/Numpy/Scipy/Matplotlib/Pillow版本与可执行路径；不改变冻结模型环境。试跑完整性结果见pilot_integrity.json；六模型全部通过，共1500请求、25500题。正式GPU未启动，未作P1–P6的成立/不成立判断。

R58 用户已明确批准完整全量（reply: “批准完整全量（剩余约43.4 GPU小时）”）。批准时预算：完整44.325197 GPU小时、已用0.948650、预计剩余43.376546。授权记录full_budget_approval.json。采用原先声明的小模型优先顺序mini/flash/OneJev/Qwen2/Qwen8/turbo；不改变六模型集合/问题/样本/seed/判定。每模型完整12864请求，复用试跑250条；预计剩余请求总数75684。每阶段启动前单独预算由owner写入本文件。

```bash
python3 -m py_compile analysis/r58_owner.py analysis/r58_launch.py analysis/r58_pipeline.py
python3 -u analysis/r58_launch.py --stage full
```

R58 GPU full 阶段开始：`vllm-sr/d3-mini`，物理GPU 3；根据200样本吞吐预计本阶段剩余2.587小时；复用已缓存样本，执行同一冻结计划。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model vllm-sr/d3-mini --stage full
```

R58 授权后报告状态更新：仅把待授权文案改为“已获用户批准，正在执行”；冻结定义、缓存和判定标准不变。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

R58 持续目标：用户明确要求“自己设置一个goal去执行”。已设置持续目标，完成条件为六模型全量缓存、冻结P1–P6/敏感性/对照及最终报告核验；预算沿用已批准的剩余约43.4 GPU小时。保持当前durable pipeline继续执行。

R58执行调度优化（科学定义不变）：每个模型的6种设置完整缓存就绪后，可用同一CPU分析命令先完成P1–P6与两取值敏感性，与后续单GPU模型阶段重叠。CPU参数、样本、题库、LOSO、bootstrap=1000及判定标准保持冻结；最终全模型CPU汇总会复用两套completion.json均成功的单元。全模型比较与正式报告仍等全部可用模型完成。CPU明确设置CUDA_VISIBLE_DEVICES为空。

可复现的单模型入口（仅在相应_full.json状态complete后执行，具体实际模型命令另记）：

```bash
python3 -u analysis/r58_launch.py --stage cpu-model --model-key <frozen_model_key>
```

R58 GPU full 阶段开始：`vllm-sr/d3-flash`，物理GPU 3；根据200样本吞吐预计本阶段剩余3.305小时；复用已缓存样本，执行同一冻结计划。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model vllm-sr/d3-flash --stage full
```

R58 d3-mini全量完整性：6×2144=12864请求，19490条二值评测记录；固定revision与manifest均匹配。GPU全量阶段实际8904.874257秒（2.474h），原试跑保留，d3-flash已自动接续。核对命令：

```bash
analysis/.venv-yestrack/bin/python - <<'PY_CACHE'
import json, sys
from pathlib import Path
sys.path.insert(0,'analysis')
from r58_metrics import Data, OUT
key='vllm-sr__d3-mini'
d=Data(key,require_full=True)
status=json.loads((OUT/'status'/(key+'_full.json')).read_text())
assert status['status']=='complete'
result={'status':'passed','model':status['model'],'revision':status['revision'],'seed':2025,
        'samples':len(d.samples),'binary_rows':d.n,'log_probability_shape':list(d.z.shape),
        'settings':{k:len(v) for k,v in d.pred.items()},'GPU_full_seconds':status['wall_seconds']}
folder=OUT/'cache_integrity';folder.mkdir(exist_ok=True)
(folder/(key+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
PY_CACHE
```

R58 d3-mini原定CPU全量分析，提前与d3-flash GPU阶段重叠；两套完成单元会由末尾CPU汇总复用。具体分析参数仍从冻结r58.json读取。

```bash
python3 -u analysis/r58_launch.py --stage cpu-model --model-key vllm-sr__d3-mini
```

R58完整缓存后的CPU分析（所有P1–P6及两取值敏感性，bootstrap1000，seed2025）：

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r58_analyze.py --model-key vllm-sr__d3-mini
```


2026-11-05 R58首个完整模型d3-mini：6种输入/措辞/顺序配置各2144请求已完整核对；原定P1–P6及两取值敏感性全部CPU计算退出0。完整模型尚为1/6，未作全模型或Qwen独特性判定。

只完善既定报告呈现：未齐全模型时保留进度报告；增加已完成全量模型的ECE/模拟噪声并列表，最终报告展示已定义的正类F1阈值效用数值。冻结指标、判定、样本和问题库不变。截断字段样本值0/1/2/未知，明确冻结数值分箱合并1/2，未新增分组。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

R58报告呈现补全：对已经冻结且由r58_analyze.py计算的P4逐属性稳定性、P5合取/正确性相关性、P6逐K/逐属性、温度折、阈值效用和crop消融增加CSV导出，并为P1/P2汇总行导出相同CI。没有新增实验或指标，没有改变判定。最终全模型报告命令由CPU owner在全部可用模型成功后执行；当前进度报告继续使用：

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```


2026-11-05 R58 Qwen缓存门槛修正（首个Qwen全量阶段前）：冻结计划明确在首个pilot样本上做0.005一致性校验。代码检查发现Qwen对象每次启动会把cache_ok重置为True，从而可能用新full样本重新决定门槛。修正为full阶段继承相同checkpoint/revision的完整pilot状态；两组Qwen的既有失败均永久走fresh reference。2B原pilot为shape错误，修复位置后的额外回归误差0.040275仍失败；8B原pilot误差0.056719失败。未修改任一既有概率、模型权重或官方源码，预算仍使用原fresh吞吐。

CPU目标回归（无模型加载、无GPU推理；直接验证真实失败pilot状态会使Qwen.predict调用fresh而非cached），输出qwen_full_cache_gate.json：

```bash
CUDA_VISIBLE_DEVICES='' PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python - <<'PY_GATE'
import json, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,'analysis')
from r58_gpu import OUT, PLAN, Qwen, reuse_qwen_pilot_cache_decision
results=[]
for info in PLAN['models']:
 if not info['repo'].startswith('Qwen/'):continue
 key=info['repo'].replace('/','__')
 calls=[]
 def cached(*args):raise AssertionError('Failed pilot gate must not invoke cached scoring during full inference')
 def fresh(*args):calls.append('fresh');return {'test':{'yes':.7,'no':.3}}
 obj=SimpleNamespace(cache_ok=True,parity=None,inputs=lambda *args:(None,None),cached=cached,fresh=fresh)
 reuse_qwen_pilot_cache_decision(obj,key,info['repo'],info['revision'])
 p,meta=Qwen.predict(obj,None,None)
 assert obj.cache_ok is False and calls==['fresh'] and p['test']['yes']==.7
 results.append({'model':info['repo'],'cache_used':obj.cache_ok,'full_readout':'fresh full-option reference',
                 'reused_pilot_gate':obj.parity,'targeted_control_flow':'passed; cached() is not called'})
record={'status':'passed','seed':2025,'GPU_inference_performed':False,'models':results}
(OUT/'qwen_full_cache_gate.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
PY_GATE
```

R58 GPU full 阶段开始：`OmniJev/OneJev1.5-9B`，物理GPU 3；根据200样本吞吐预计本阶段剩余0.985小时；复用已缓存样本，执行同一冻结计划。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model OmniJev/OneJev1.5-9B --stage full
```

R58 d3-flash完整缓存核对（所有6种设置），全量GPU阶段实际11762.843秒（3.267h）；OneJev GPU阶段已自动接续。

```bash
/data2/user/LocateMOT_GroundJEV/.python/cpython-3.12.15-linux-x86_64-gnu/bin/python3.12 -c 'import json,sys
from pathlib import Path
sys.path.insert(0,'"'"'analysis'"'"')
from r58_metrics import Data, OUT
key='"'"'vllm-sr__d3-flash'"'"'
d=Data(key,require_full=True)
status=json.loads((OUT/'"'"'status'"'"'/(key+'"'"'_full.json'"'"')).read_text())
assert status['"'"'status'"'"']=='"'"'complete'"'"'
result={'"'"'status'"'"':'"'"'passed'"'"','"'"'model'"'"':status['"'"'model'"'"'],'"'"'revision'"'"':status['"'"'revision'"'"'],'"'"'seed'"'"':2025,
 '"'"'samples'"'"':len(d.samples),'"'"'binary_rows'"'"':d.n,'"'"'log_probability_shape'"'"':list(d.z.shape),
 '"'"'settings'"'"':{k:len(v) for k,v in d.pred.items()},'"'"'GPU_full_seconds'"'"':status['"'"'wall_seconds'"'"']}
folder=OUT/'"'"'cache_integrity'"'"';folder.mkdir(exist_ok=True)
(folder/(key+'"'"'.json'"'"')).write_text(json.dumps(result,indent=2)+chr(10))
print(json.dumps(result))
'
```

R58 d3-flash缓存核对命令失败归因：Path.resolve()把venv解释器符号链接解析到裸Python，触发ModuleNotFoundError: numpy；在读取概率或启动CPU分析前退出。只修正为保留venv入口，继续同一缓存核对。

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -c 'import json,sys
from pathlib import Path
sys.path.insert(0,'"'"'analysis'"'"')
from r58_metrics import Data, OUT
key='"'"'vllm-sr__d3-flash'"'"'
d=Data(key,require_full=True)
status=json.loads((OUT/'"'"'status'"'"'/(key+'"'"'_full.json'"'"')).read_text())
assert status['"'"'status'"'"']=='"'"'complete'"'"'
result={'"'"'status'"'"':'"'"'passed'"'"','"'"'model'"'"':status['"'"'model'"'"'],'"'"'revision'"'"':status['"'"'revision'"'"'],'"'"'seed'"'"':2025,
 '"'"'samples'"'"':len(d.samples),'"'"'binary_rows'"'"':d.n,'"'"'log_probability_shape'"'"':list(d.z.shape),
 '"'"'settings'"'"':{k:len(v) for k,v in d.pred.items()},'"'"'GPU_full_seconds'"'"':status['"'"'wall_seconds'"'"']}
folder=OUT/'"'"'cache_integrity'"'"';folder.mkdir(exist_ok=True)
(folder/(key+'"'"'.json'"'"')).write_text(json.dumps(result,indent=2)+chr(10))
print(json.dumps(result))
'
```

R58 d3-flash原定CPU分析：P1–P6及两取值敏感性，seed2025/轨迹bootstrap1000，与后续GPU阶段并行。

```bash
python3 -u analysis/r58_launch.py --stage cpu-model --model-key vllm-sr__d3-flash
```

R58完整缓存后的CPU分析（所有P1–P6及两取值敏感性，bootstrap1000，seed2025）：

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r58_analyze.py --model-key vllm-sr__d3-flash
```


2026-11-05 R58 d3-flash完整CPU结果已完成（两套completion均为seed2025/bootstrap1000；主2144样本/19490二值记录，严格2111样本/19016记录）。缓存核对的venv路径问题修正后目标检查通过，未重新运行GPU。更新进度报告为2/6。

报告呈现补全：既定P5配对NLL区间、P6各K的N、预定义的决策模型-Qwen配对差值表直接展示；严格版二元1799/三元0的空组范围明确披露。没有新增指标、分组或判定标准。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

R58最终报告章节对齐用户交付顺序：①数据、②模型及P1–P6表/图、③冻结标准逐项、④Qwen对照、⑤一句话。仅调整呈现，进度版按同一命令更新：

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

R58 GPU full 阶段开始：`Qwen/Qwen3-VL-2B-Instruct`，物理GPU 3；根据200样本吞吐预计本阶段剩余10.808小时；复用已缓存样本，执行同一冻结计划。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model Qwen/Qwen3-VL-2B-Instruct --stage full
```

R58 OneJev1.5-9B完整缓存核对，全量GPU实际3389.982秒（0.942h）；Qwen2已自动接续。

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -c 'import json,sys
from pathlib import Path
sys.path.insert(0,'"'"'analysis'"'"')
from r58_metrics import Data, OUT
key=sys.argv[1]
d=Data(key,require_full=True)
status=json.loads((OUT/'"'"'status'"'"'/(key+'"'"'_full.json'"'"')).read_text())
assert status['"'"'status'"'"']=='"'"'complete'"'"'
result={'"'"'status'"'"':'"'"'passed'"'"','"'"'model'"'"':status['"'"'model'"'"'],'"'"'revision'"'"':status['"'"'revision'"'"'],'"'"'seed'"'"':2025,
 '"'"'samples'"'"':len(d.samples),'"'"'binary_rows'"'"':d.n,'"'"'log_probability_shape'"'"':list(d.z.shape),
 '"'"'settings'"'"':{k:len(v) for k,v in d.pred.items()},'"'"'GPU_full_seconds'"'"':status['"'"'wall_seconds'"'"']}
folder=OUT/'"'"'cache_integrity'"'"';folder.mkdir(exist_ok=True)
(folder/(key+'"'"'.json'"'"')).write_text(json.dumps(result,indent=2)+chr(10))
print(json.dumps(result))
' OmniJev__OneJev1.5-9B
```

R58 OneJev1.5-9B原定CPU分析：P1–P6及两取值敏感性，seed2025/轨迹bootstrap1000，与后续Qwen GPU阶段并行。

```bash
python3 -u analysis/r58_launch.py --stage cpu-model --model-key OmniJev__OneJev1.5-9B
```

R58完整缓存后的CPU分析（所有P1–P6及两取值敏感性，bootstrap1000，seed2025）：

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r58_analyze.py --model-key OmniJev__OneJev1.5-9B
```

2026-11-05 R58 OneJev1.5-9B主/严格两套CPU分析完成，缓存核对通过，进度报告3/6。补充已有标准在敏感性口径下的逐项判定变化，避免整体判定相同掩盖子项变化；不增删指标或门槛。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```


2026-11-05 R58执行调度：Qwen2B的main配置已覆盖全部2144样本，GPU继续其余5种冻结设置。现先计算同一全量main所需的既定P1/P2/P3/P5/P6及阈值效用（含两取值敏感性），只缓存main_completion.json，P4/crop及全模型completion仍待其余设置齐备。没有新增实验、样本、问题、拟合参数或判定标准。完整阶段重新核对6种设置，并验证原始z/selected/y/序列/轨迹/属性与OOF检查点逐值相同后复用CPU结果，补齐P4/crop。

CPU缓存恢复目标回归：使用原已完成d3-mini的真实OOF作为参考，按保存的逐折T从原始分数重算，最大概率误差0；Qwen2主配置读取2144样本/19490二值记录，仅加载main。无GPU推理。输出main_checkpoint_regression.json。

```bash
CUDA_VISIBLE_DEVICES='' analysis/.venv-yestrack/bin/python - <<'PY_MAIN_CHECK'
import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'analysis')
from r58_metrics import Data,OUT,probability
from r58_analyze import load_main_checkpoint
key='vllm-sr__d3-mini'
d=Data(key,require_full=True,main_only=True)
assert set(d.pred)=={'main'}
p,temperatures=load_main_checkpoint(d,OUT/'metrics'/key)
expected=np.empty(d.n)
for (seq,_),T in temperatures.items():
 ix=d.seq==seq
 expected[ix]=probability(d.z[ix],d.selected[ix],T)
error=float(np.max(np.abs(p-expected)))
assert error==0.,error
q=Data('Qwen__Qwen3-VL-2B-Instruct',require_full=True,main_only=True)
result={'status':'passed','seed':2025,'GPU_inference_performed':False,
        'reference_model':key,'checkpoint_input_arrays':'z, selected, y, sequence, track, attribute exactly equal',
        'replayed_global_probability_max_abs_error':error,
        'Qwen2_main_samples':len(q.pred['main']),'Qwen2_binary_rows':q.n,
        'only_main_loaded':list(q.pred),'full_model_completion_claimed':False}
(OUT/'main_checkpoint_regression.json').write_text(json.dumps(result,indent=2)+chr(10))
print(json.dumps(result))
PY_MAIN_CHECK
```

Qwen2B既定main配置CPU阶段（全量main，seed2025，bootstrap1000；该阶段完成不等于该模型全部分析完成）：

```bash
python3 -u analysis/r58_launch.py --stage cpu-main --model-key Qwen__Qwen3-VL-2B-Instruct
```

R58既定CPU分析（完整main设置：P1/P2/P3/P5/P6及效用；P4/crop待对应缓存，bootstrap1000，seed2025）：

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r58_analyze.py --model-key Qwen__Qwen3-VL-2B-Instruct --main-only
```

R58输入几何抽查（只读；不是新实验或人工标签审计）：按冻结manifest顺序，各取首个Car且vehicle_colour已知、框高<40和>100样本，分别0000:6:124及0000:1:129。用view_image查看各自inputs/*_frame.jpg及*_crop.jpg，目标区域对应；小框遮挡明显，大框车身清晰。记录input_geometry_check.json；属性标签及人工CSV空字段均未改动。

R58 Qwen2 main-CPU终端观察会话退出143：按/proc中的实际命令行和cwd确认owner PID2594939及analysis PID2594941仍活跃，GPU父流水线亦在运行；没有据观察会话退出重启任务。新增单个阻塞接续命令，内部跟随同一PID和durable日志，结束时核验其结果；不作agent级进程轮询。

```bash
python3 -u analysis/r58_wait_cpu.py --model-key Qwen__Qwen3-VL-2B-Instruct --main-only
```

R58进度呈现：Qwen2全量main的原定CPU核心分析完成，正常completion仍待P4/crop。报告增加main-only表并区别有限样本ECE噪声与标签噪声，不改变任何冻结定义或指标。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

R58 GPU full 阶段开始：`Qwen/Qwen3-VL-8B-Instruct`，物理GPU 6；根据200样本吞吐预计本阶段剩余23.485小时；复用已缓存样本，执行同一冻结计划。

```bash
CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model Qwen/Qwen3-VL-8B-Instruct --stage full
```

R58 Qwen3-VL-2B全量GPU完成，实际39026.902秒（10.841h）；核对6×2144完整缓存后补齐P4/crop，复用已逐值验证的main CPU检查点。Qwen8已按原流水线接续，物理GPU6，预算沿用冻结试跑估计。

```bash
analysis/.venv-yestrack/bin/python - <<'PY_CACHE_CHECK'
import json,sys
sys.path.insert(0,'analysis')
from r58_metrics import Data,OUT
key='Qwen__Qwen3-VL-2B-Instruct'
d=Data(key,require_full=True)
status=json.loads((OUT/'status'/(key+'_full.json')).read_text())
assert status['status']=='complete'
result={'status':'passed','model':status['model'],'revision':status['revision'],'seed':2025,
        'samples':len(d.samples),'binary_rows':d.n,'log_probability_shape':list(d.z.shape),
        'settings':{k:len(v) for k,v in d.pred.items()},'GPU_full_seconds':status['wall_seconds']}
folder=OUT/'cache_integrity';folder.mkdir(exist_ok=True)
(folder/(key+'.json')).write_text(json.dumps(result,indent=2)+chr(10))
print(json.dumps(result))
PY_CACHE_CHECK
```

R58 Qwen2完整CPU阶段（只补既定P4/crop并核对复用main；含两取值敏感性，seed2025/bootstrap1000）：

```bash
python3 -u analysis/r58_launch.py --stage cpu-model --model-key Qwen__Qwen3-VL-2B-Instruct
```

R58既定CPU分析（所有P1–P6及两取值敏感性，bootstrap1000，seed2025）：

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r58_analyze.py --model-key Qwen__Qwen3-VL-2B-Instruct
```

R58 Qwen2全量CPU结果核验：最初只读检查误按status字段读取completion.json而退出KeyError；实际标志字段为complete。改用complete==true、seed2025、bootstrap1000检查后，主2144/19490与严格2111/19016均通过，无实验重跑或数据改动。两幅既定可靠性图已用view_image查看。进度报告更新为4/6完整模型：

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

R58 Qwen8性能诊断：GPU6与另一个任务共享计算，前140条全量请求3561.981秒，约25.44秒/条；pilot在GPU3约6.97秒/条。一次资源快照GPU6利用率100%且有另一进程；GPU3约24%，显存充足。只修改analysis执行调度：在满足允许GPU/显存/项目≤4GPU条件后，优先低利用率，显存作次序；冻结plan不变。先做无GPU选择逻辑回归，再停止且仅停止本任务3个已核实PID，保留所有完整JSONL，重启原同一pipeline从未完成单元继续。不中断其它任务，不改变模型/题库/分数逻辑。原部分GPU耗时另存resource_handoff_Qwen8.json，最终实际耗时须计入。

```bash
python3 - <<'PY_RESOURCE_CHECK'
import json,sys
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,'analysis')
import r58_owner as owner
from pathlib import Path
gpus=SimpleNamespace(stdout='3, g3, 56320, 24\n4, g4, 10240, 0\n6, g6, 61440, 100\n')
apps=SimpleNamespace(stdout='')
with patch.object(owner.subprocess,'run',side_effect=[gpus,apps,gpus,apps]):
 preferred=owner.select_gpu(28);large=owner.select_gpu(60)
assert preferred==3 and large==6
result={'status':'passed','low_utilization_preferred_when_memory_sufficient':preferred,'memory_requirement_still_enforced':large,'GPU_inference_performed':False}
Path('analysis/runs/R58_calibration/resource_selection_check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
PY_RESOURCE_CHECK
```

```bash
python3 -u analysis/r58_handoff.py --pipeline 2090465 --owner 2090466 --worker 3132489
```

恢复估计：若接近原pilot吞吐，Qwen8剩余约23小时；负载变化仍会影响实际耗时。沿用用户已批准完整全量授权，不新增实验。新worker启动前owner仍将记录具体CUDA_VISIBLE_DEVICES及原预算估计。

```bash
python3 -u analysis/r58_launch.py --stage full
```

R58 GPU full 阶段开始：`Qwen/Qwen3-VL-8B-Instruct`，物理GPU 3；根据200样本吞吐预计本阶段剩余23.485小时；复用已缓存样本，执行同一冻结计划。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model Qwen/Qwen3-VL-8B-Instruct --stage full
```

R58 Qwen8迁移后原请求吞吐约10秒/条，优于GPU6的25.44秒/条；main2144已齐备，保留迁移前367条main。其余5配置继续GPU，先执行既定main核心CPU分析，完整completion仍等待P4/crop。全局T/seed/LOSO/1000轨迹bootstrap/所有判定未变，不将该阶段当模型完成。

```bash
analysis/.venv-yestrack/bin/python - <<'PY_MAIN_CACHE'
import json,sys
sys.path.insert(0,'analysis')
from r58_metrics import Data,OUT
key='Qwen__Qwen3-VL-8B-Instruct';d=Data(key,require_full=True,main_only=True)
assert set(d.pred)=={'main'} and len(d.pred['main'])==2144
result={'status':'passed','seed':2025,'model':key,'samples':len(d.samples),'binary_rows':d.n,'only_main_loaded':list(d.pred),'full_model_completion_claimed':False}
p=OUT/'main_cache_integrity';p.mkdir(exist_ok=True)
(p/(key+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
PY_MAIN_CACHE
```

```bash
python3 -u analysis/r58_launch.py --stage cpu-main --model-key Qwen__Qwen3-VL-8B-Instruct
```

R58既定CPU分析（完整main设置：P1/P2/P3/P5/P6及效用；P4/crop待对应缓存，bootstrap1000，seed2025）：

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r58_analyze.py --model-key Qwen__Qwen3-VL-8B-Instruct --main-only
```

R58 Qwen8完整main核心CPU分析及两取值敏感性成功，正常模型completion仍待P4/crop。main-only标志、2144/19490与2111/19016、seed2025/bootstrap1000均核对。既定指标进度表更新，不新增实验/判定：

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

R58 GPU full 阶段开始：`vllm-sr/d3-turbo`，物理GPU 3；根据200样本吞吐预计本阶段剩余2.207小时；复用已缓存样本，执行同一冻结计划。

```bash
CUDA_VISIBLE_DEVICES=3 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONPATH=/home/user/.cache/r58_calibration/extra310 /data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python -u analysis/r58_gpu.py --model vllm-sr/d3-turbo --stage full
```

R58 Qwen8六配置GPU完成，恢复worker97108.258秒，加迁移前4280.520秒，总全量GPU阶段101388.778秒（28.164h，pilot另计）。原GPU负载变化导致高于启动前23.485h外推，未改变实验。Turbo已按原计划接续GPU3。先核对Qwen8全量，再补P4/crop，复用主/严格既定main CPU检查点。

```bash
analysis/.venv-yestrack/bin/python - <<'PY_CACHE_CHECK'
import json,sys
sys.path.insert(0,'analysis')
from r58_metrics import Data,OUT
key='Qwen__Qwen3-VL-8B-Instruct';d=Data(key,require_full=True)
s=json.loads((OUT/'status'/(key+'_full.json')).read_text());assert s['status']=='complete'
h=json.loads((OUT/'resource_handoff_Qwen8.json').read_text())
result={'status':'passed','model':s['model'],'revision':s['revision'],'seed':2025,
 'samples':len(d.samples),'binary_rows':d.n,'log_probability_shape':list(d.z.shape),
 'settings':{k:len(v) for k,v in d.pred.items()},'GPU_successful_resume_seconds':s['wall_seconds'],
 'prior_interrupted_worker_seconds':h['interrupted_worker_elapsed_seconds'],
 'GPU_full_total_seconds':s['wall_seconds']+h['interrupted_worker_elapsed_seconds']}
p=OUT/'cache_integrity';p.mkdir(exist_ok=True)
(p/(key+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
PY_CACHE_CHECK
```

```bash
python3 -u analysis/r58_launch.py --stage cpu-model --model-key Qwen__Qwen3-VL-8B-Instruct
```

R58既定CPU分析（所有P1–P6及两取值敏感性，bootstrap1000，seed2025）：

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r58_analyze.py --model-key Qwen__Qwen3-VL-8B-Instruct
```

R58 Qwen8完整CPU标志、seed2025/1000 bootstrap及主/严格样本数核对通过，进度报告5/6。呈现补充：实际GPU阶段计时（含迁移前工作，不把未完成记0）、全部模型原定指标概览、区分“部分成立”标签与数值排名；没有新增实验或门槛。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py --pending
```

R58既定CPU分析（所有P1–P6及两取值敏感性，bootstrap1000，seed2025）：

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python -u analysis/r58_analyze.py --model-key vllm-sr__d3-turbo
```

R58最后GPU阶段d3-turbo完成，7846.976秒（2.180h），原发布BF16未触发量化回退。核对全部6×2144完整缓存；原同一pipeline已自动复用前5个完整CPU模型并执行Turbo两套CPU分析，不另启动CPU owner。

```bash
analysis/.venv-yestrack/bin/python - <<'PY_CACHE_CHECK'
import json,sys
sys.path.insert(0,'analysis')
from r58_metrics import Data,OUT
key='vllm-sr__d3-turbo';d=Data(key,require_full=True)
s=json.loads((OUT/'status'/(key+'_full.json')).read_text());assert s['status']=='complete'
result={'status':'passed','model':s['model'],'revision':s['revision'],'seed':2025,
 'samples':len(d.samples),'binary_rows':d.n,'log_probability_shape':list(d.z.shape),
 'settings':{k:len(v) for k,v in d.pred.items()},'GPU_full_seconds':s['wall_seconds']}
p=OUT/'cache_integrity';p.mkdir(exist_ok=True)
(p/(key+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
PY_CACHE_CHECK
```

R58汇总报告与配对模型比较：

```bash
/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/.venv-yestrack/bin/python analysis/r58_report.py
```

R58六个可运行模型全部GPU/两套CPU分析完成，pipeline_status.complete。最终报告补充原定P1–P6的数字解释、每属性T次要表、最大样本正确性相关对、配对Qwen差值解读和审计范围；所有数值仍直接读取冻结统计，不新增实验/阈值/样本。ECE概览统一并列MC噪声；说明无标签训练折的每属性T不可评、0.5并非F1一般最优阈值。人工标签未修改。

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py
```

最终官方源码核对：首次在analysis/upstream母目录误查了GroundJEV工作树的既有未提交变更，随后明确具体YesTrack与OneJev子仓库，两者diff HEAD为空，HEAD分别ed42b8315b28c94dc595d83b0d49bf57002bb281/2470c7595688c6a402560cf18b4753feb1fe290a。没有回滚或操作其它项目变更。可复核：

```bash
git -C analysis/upstream/YesTrack diff HEAD --exit-code
git -C /data2/user/LocateMOT_GroundJEV/external/OneJev diff HEAD --exit-code
```

R58最终交付完整性核对：只读已有缓存/标签/OOF和报告附表，不跑GPU、不调参。核对6模型×6配置、固定revision、主/严格两套完成标志与1000轨迹bootstrap、跨模型二值记录逐值一致、17个train序列、50表达式及693属性图片审计、派生缓存≤25GiB；输出final_integrity.json。官方源码clean依据前述实际子仓库diff HEAD检查，不重复检查父工作树。

```bash
analysis/.venv-yestrack/bin/python - <<'PY_FINAL_CHECK'
import csv,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'analysis')
from r58_metrics import OUT,TASK

def read(p):return json.loads(p.read_text())
plan=read(TASK/'analysis/plans/r58.json');samples=read(OUT/'samples.json')
assert plan['status']=='FROZEN_BEFORE_ANY_MODEL_INFERENCE' and plan['seed']==2025
assert len(samples)==2144 and set(s['sequence'] for s in samples)==set(plan['sequences'])
assert not set(plan['sequences']) & {'0005','0011','0013','0019'}
assert read(OUT/'pipeline_status.json')['status']=='complete'
models=[m for m in read(OUT/'pilot_owner_result.json')['models'] if m['status']=='complete']
assert len(models)==6
settings={s['id'] for s in plan['questions']['settings']};assert len(settings)==6
reference={};checks=[];total=0
for model in models:
 key=model['checkpoint_repo'].replace('/','__');cache=read(OUT/'cache_integrity'/(key+'.json'))
 assert cache['status']=='passed' and set(cache['settings'])==settings and set(cache['settings'].values())=={2144}
 status=read(OUT/'status'/(key+'_full.json'))
 pin=next(m['revision'] for m in plan['models'] if m['repo']==model['checkpoint_repo'])
 assert status['status']=='complete' and status['revision']==pin
 total+=sum(cache['settings'].values())
 for regime,folder,n,images in [('main',OUT/'metrics'/key,19490,2144),('two_values',OUT/'metrics'/key/'sensitivity_two_values',19016,2111)]:
  meta=read(folder/'completion.json')
  assert meta['complete'] and meta['seed']==2025 and meta['bootstrap']==1000 and meta['binary_rows']==n and meta['samples']==images
  for name in ['P1_P2','P3','P4','P5','P6','P5_correctness_correlations','decision_utility','crop_ablation']:
   assert (folder/(name+'.json')).is_file()
  p=read(folder/'P1_P2.json')
  assert {r['held_out'] for r in p['temperatures']}==set(plan['sequences'])
  for a in plan['samples']['main_attributes']:
   m=p['attributes']['global_T_LOSO'][a]
   assert m['N']>0 and all(k in m for k in ['ECE_mass15','ECE_width15','ECE_mass15_noise','ECE_width15_noise','cluster_bootstrap95','Brier_decomposition_mass','Brier_decomposition_width'])
  rows=read(folder/'rows.json');oof=np.load(folder/'OOF.npz')
  identity=[(r['sample_id'],r['attribute'],r['value'],r['y']) for r in rows]
  assert len(rows)==n and np.isfinite(oof['p_global']).all() and np.all((oof['p_global']>=0)&(oof['p_global']<=1))
  assert np.array_equal(oof['y'],[r['y'] for r in rows])
  if regime in reference:assert identity==reference[regime]
  else:reference[regime]=identity
  for a in ['category','vehicle_colour']:assert (folder/'figures'/('reliability_'+a+'.png')).is_file()
 checks.append({'model':model['model'],'revision':pin,'requests':sum(cache['settings'].values()),'primary_binary_rows':19490,'strict_binary_rows':19016})
assert total==77184 and len(plan['questions']['bank'])==17
with (OUT/'label_audit.csv').open() as f:audit=list(csv.DictReader(f))
with (OUT/'label_noise_audit.csv').open() as f:noise=list(csv.DictReader(f))
assert len(audit)==50 and len(noise)==693 and all(Path(r['image']).is_file() for r in noise)
feature_bytes=sum(p.stat().st_size for name in ['inputs','predictions','metrics','label_noise_audit'] for p in (OUT/name).rglob('*') if p.is_file())
assert feature_bytes<=plan['resources']['temporary_features_bytes_limit']
consensus=read(OUT/'report_tables/consensus_noise_reference.json')
assert set(consensus['models_included'])=={m['checkpoint_repo'].replace('/','__') for m in models}
judgments=read(OUT/'report_tables/formal_model_judgments.json');assert len(judgments)==6
required_tables=['all_metrics.csv','P3_subgroups.csv','temperature_folds.csv','P4_wording.csv','P5_composition.csv','P5_correctness_correlations.csv','P6_temporal.csv','decision_utility.csv','decision_utility_folds.csv','crop_ablation.csv','formal_criteria.csv','decision_vs_Qwen_paired.json']
assert all((OUT/'report_tables'/f).is_file() for f in required_tables)
result={'status':'passed','seed':2025,'train_sequences':plan['sequences'],'validation_sequences_in_manifest':[],
 'models':checks,'total_requests':total,'questions_per_request':17,'scored_questions':total*17,
 'CPU_regimes':['main','two_values'],'bootstrap':1000,'binary_row_identity_equal_across_models':True,
 'expression_audit_rows':len(audit),'label_noise_audit_rows':len(noise),'human_audit_rows_filled':sum(bool(r['human_y'].strip()) for r in noise),
 'derived_disk_bytes_excluding_raw_weights':feature_bytes,'derived_GiB':feature_bytes/2**30,
 'full_criteria_pass_count':sum(j['overall']=='成立' for j in judgments),
 'GPU_stage_hours_including_pilot_and_handoff':read(OUT/'gpu_actual_timing.json')['total_GPU_stage_seconds']/3600,
 'official_sources_observed_clean':{'YesTrack':{'HEAD':'ed42b8315b28c94dc595d83b0d49bf57002bb281','diff_HEAD_exit_code':0},'OneJev':{'HEAD':'2470c7595688c6a402560cf18b4753feb1fe290a','diff_HEAD_exit_code':0}},
 'report':str(TASK/'analysis/REPORT_R58.md')}
(OUT/'final_integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
PY_FINAL_CHECK
```

R58最终报告呈现复核：补上8896/1255表达式统计、77184请求/1312128题覆盖、原始ECE对应MC噪声、无标签训练折不可评说明与段落分隔。仅报告生成改变，数值缓存/统计/判定未改；final_integrity.json已通过，代表性Qwen2及Turbo可靠性图已目视检查。最终生成：

```bash
analysis/.venv-yestrack/bin/python analysis/r58_report.py
```

NAS20261112（非模型实验）：只读盘点，不迁移。

```bash
python3 -u analysis/nas_inventory_20261112/scan_migration.py
```

NAS20261112 分类复核：initial元数据保留；latest_training_state与推理权重分列，identity_memory/runtime/评测pth归结果，examples.pt归派生训练资料；排除GroundAnything内嵌HF原始数据缓存。仅处理CSV，不重跑实验、不读tensor、不迁移源文件。

```bash
python3 analysis/nas_inventory_20261112/finalize_inventory.py
```

NAS20261112 元数据汇总首轮因Path.parents重复构造耗时偏长；只中断本次finalize进程722046（SIGINT，退出130），initial文件与源文件保留。词法路径包含判断改用带目录边界的前缀（包含/相邻目录对照一致），同时将features/*.pt归派生特征、checkpoints/rng归恢复状态。重跑仅汇总：

```bash
python3 analysis/nas_inventory_20261112/finalize_inventory.py
```

NAS20261112 最终分类核对：发布包中的refer_gt/官方预测属于评测证据，仅v1bestweight/v2bestweight归发布权重；未增加/删除任何源文件。导出独立code_files/project_checkpoints清单。最终命令（cwd=YesTrack任务目录）：

```bash
set -o pipefail
python3 analysis/nas_inventory_20261112/finalize_inventory.py | tee analysis/nas_inventory_20261112/finalization.log
```

NAS20261112 最终容量与清单核对通过：files唯一inode/分类/physical_sources/权重分组均加和一致；结果见nas_inventory_20261112/validation.json。原始数据缓存另剔除51文件/3.271GiB；不迁移、不清理。报告与精确容量由上条finalize命令重放initial快照生成，未来重新盘点须用新日期目录。

2026-11-12 checkpoint重要性审计开始：基于NAS已有元数据，先读导出/merge代码及训练回执，按正式终点、研究对照、当前依赖和可恢复性筛选；旧文档状态与实际回执交叉核对。仅生成优先保留/暂缓/待确认清单，不删文件、不迁移、不改模型。新输出analysis/nas_inventory_20261112/checkpoint_audit/。

NAS checkpoint审计：依据实际完成回执、评测引用及export/merge依赖筛选。只生成checkpoint_audit独立清单，原inventory/实验结果/权重不改。命令（CPU，不读tensor、不推理）：

```bash
set -o pipefail
python3 analysis/nas_inventory_20261112/checkpoint_audit/audit_checkpoints.py | tee analysis/nas_inventory_20261112/checkpoint_audit/audit.log
```

NAS checkpoint审计最终复核：不靠文件名认证终点；补入实际G2 independent comparison、旧G1 delta在两个工作树均缺失的存在性检查；逐一核对暂缓完整导出的替代依赖与保留模型config，在线functional_resume_state归附件。仅重生成独立审计清单：

```bash
set -o pipefail
python3 analysis/nas_inventory_20261112/checkpoint_audit/audit_checkpoints.py | tee analysis/nas_inventory_20261112/checkpoint_audit/audit_final.log
```

2026-11-12 checkpoint重要性审计完成（仅建议，不删不迁移）：原清单382项项目权重加恢复状态/发布模型配套共1034项719.100GiB；优先172项51.865GiB，另配套237文件，总精简清单409文件/52.683GiB；暂缓855项649.875GiB；待确认7项17.361GiB。项目权重保留34.423GiB，覆盖G2正式18227/耦合11000-17000-17500/中期portable、OneJev500/native-teacher600/broader6000/history成对对照/8227LoRA及准确native600底座、旧U1U2/官方YesTrack LoRA和小型研究头。大型工程探针、中间全模型、非优先Adam备份、可再导出的包及可重下载公开大模型暂缓；旧G1 delta两工作树均缺失、未完成旧课程等单列待确认。保留一个G2终点和0.12GiB8227恢复备份；没有把BF16权重等同FP32/Adam恢复。暂缓完整导出依赖闭合、选中config/存在性/大小/inode/容量核对通过，未重载tensor/未做推理或全量内容hash；原inventory/实验结果不改。详情analysis/nas_inventory_20261112/checkpoint_audit/REPORT.md和migration_keep_files.csv。

2026-11-12 用户批准移动已审计精选checkpoint。NAS A800已挂载可写，可用约3.3TiB；独立目标/data2/user/nas/A800/selected_checkpoints/LocateMOT_20261112/，不触碰正在运行的全盘_migration_control备份。仅409文件/56567703095字节；CPU双文件并发复制、完整SHA256读回核验后，将原文件和本项目范围内已识别硬链接别名原子替换为NAS符号链接，保持原路径可用。先冻结逐文件plan和别名，逐单元保存verified/completed，可从未完成单元恢复；不迁移暂缓/待确认独立权重，不改权重内容、不改官方推理逻辑，不用GPU。

```bash
set -o pipefail
python3 -u analysis/nas_inventory_20261112/checkpoint_audit/transfer_to_nas.py | tee analysis/nas_inventory_20261112/checkpoint_audit/transfer_20261112.log
```

NAS传输性能修正：SSHFS2.8写入约1–2MiB/s，运行262秒只写0.32GiB、零文件完成/零源路径替换。仅中断本任务PID2018483（SIGINT，退出130），保留plan及partial。现有端点按README仅支持SFTP，未改写全盘备份/挂载/权限。读取本机Paramiko2.6.0接口后，用同一个已固定host key的SFTP端点，试验pipelined write和有界readv预取（8MiB窗口），输入为精选清单中43MB最终adapter；核验后删除本次pilot临时副本，源文件不改。

```bash
set -o pipefail
python3 analysis/nas_inventory_20261112/checkpoint_audit/sftp_transport.py | tee analysis/nas_inventory_20261112/checkpoint_audit/transfer_20261112/sftp_pilot.log
```

SFTP单连接pilot内容核验通过：43,346,432字节，上传1.341MiB/s/读回3.086MiB/s，未移动源文件。进一步对实际156MB G2 portable adapter试用同一受限SFTP端点上的8持久连接、每文件最多4个32MiB分块；按offset写入，按offset有序读回做完整文件SHA256，内存有界，无模型逻辑/内容改动。

```bash
set -o pipefail
python3 analysis/nas_inventory_20261112/checkpoint_audit/sftp_transport.py | tee analysis/nas_inventory_20261112/checkpoint_audit/transfer_20261112/sftp_parallel_pilot.log
```

并发SFTP pilot内容核验通过：156389221字节，上传1.573MiB/s、读回6.574MiB/s；带完整读回的52.68GiB仍约需12小时。已向用户请求跨任务消息授权，尚未向NAS任务发消息；完整manifest/分块脚本已就绪。独立CPU准备409文件源端SHA256与精确rsync文件列表，并将不能从dataN共享读取的home模型配置暂存到本项目analysis（小型配套文件），不启动NAS任务、不改源文件：

```bash
set -o pipefail
python3 -u analysis/nas_inventory_20261112/checkpoint_audit/prepare_nas_pull.py | tee analysis/nas_inventory_20261112/checkpoint_audit/transfer_20261112/nas_pull_preparation.log
```

2026-11-12 用户明确授权“NAS任务接手”。已向现有NAS任务“核查 NAS 文件路径与大小”（01a12b7b-30ad-7ff2-a097-fb1f65f76c0f，nas57）发送精确409文件/56567703095字节、SHA256和两批files0清单。NAS通过已有只读rsync直连拉取，在独立selected_checkpoints/LocateMOT_20261112目录逐文件本地校验并写回执；不得修改全盘备份或A800原文件。A800在完整回执核对后才原子切换458原路径。源端SHA256计算45.47秒；home临时配套11文件/1132字节。没有重启慢速SFTP完整传输。

NAS直拉最终切换：新增finalize_nas_pull.py，仅在NAS409条完整SHA256回执与A800源哈希一致、目标大小正确、458个原路径身份未变时执行原子链接替换。保留verified/completed逐文件journal；清理仅本次未完成.partial。单次阻塞等待脚本读取NAS状态，每30秒在shell内报告一次，不进行agent层进程轮询；NAS失败立即退出，不跳文件。命令（cwd=YesTrack任务目录，CPU）：

```bash
set -o pipefail
python3 -u analysis/nas_inventory_20261112/checkpoint_audit/wait_and_finalize_nas_pull.py | tee analysis/nas_inventory_20261112/checkpoint_audit/transfer_20261112/nas_pull_finalize.log
```

NAS任务已接手且两批dry-run通过，实际传输继续。A800等待器改由独立user systemd服务托管，避免终端断开影响已批准的校验后迁移；仅停止本任务旧等待器，不停止NAS拉取或全盘备份。服务命令：

```bash
systemd-run --user --unit=locatemot-selected-ckpt-finalize-20261112 '--description=Finalize approved LocateMOT checkpoints after NAS SHA256 receipt' --working-directory=/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101 --property=StandardOutput=append:/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/nas_inventory_20261112/checkpoint_audit/transfer_20261112/nas_pull_finalize_service.log --property=StandardError=inherit /usr/bin/python3 -u /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/nas_inventory_20261112/checkpoint_audit/wait_and_finalize_nas_pull.py
```

2026-11-12 NAS精选迁移交接完成、传输尚在进行：NAS两批小型dry-run通过，独立rsync任务已启动。A800最终等待/切换服务locatemot-selected-ckpt-finalize-20261112.service已验证ActiveState=active/SubState=running（MainPID2809170）。仅旧等待器2658139被停止，NAS拉取和原有全盘备份未中断；全部源在NAS校验通过前保留。NAS任务已收到补充要求：等待A800最终status.json=complete，复核migration_receipt409行与source_aliases458行后才视为全流程交付。当前不宣称迁移已完成；最终回执由服务写入本地transfer_20261112与NAS独立目标目录。全过程不使用GPU、不改模型内容。

2026-11-12 持续监控目标已建立：NAS状态仍为running/copying，使用4路精确分片，errors为空、source_files_modified=false；A800最终化服务仍active/running。启动一个单次阻塞监控器（内部每60秒读取NAS状态、A800本地status和finalizer service，不重启传输）；监控器仅在NAS失败、finalizer失败或最终status=complete时退出。命令：

```bash
python3 -u - <<'PY'
# 读取 nas_pull_status.json、transfer_20261112/status.json 和
# locatemot-selected-ckpt-finalize-20261112.service，直至成功或失败。
PY
```

## NAS补传 2026-11-15：补齐真实覆盖缺口（CPU，seed=2025）

目的：备份遗漏的GroundJEV/旧U2评测trace、外置训练运行证据、R58原始预测、上次快照后的代码/日志及迁移控制回执。冻结范围以analysis/nas_followup_20261115/plan.json为准；不改既有实验或源文件，使用gzip level 1和两路CPU，逐包完整NAS读回检验每个文件SHA256。无GPU耗时。命令工作目录为GroundJEV项目根。

```bash
python3 -m py_compile yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py prepare
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py run
```

### NAS补传：运行修复与续传记录（CPU，无新模型推理）

plan_v1保留；plan_amendment_v2明确列出4个UI临时引用的排除和两份共享文档的固定副本。有效范围36305文件、100702571726源字节、58个包。未改变任何实验样本/模型/阈值/seed/统计指标。连接诊断、失败输入审计、缓存与正偏移续传回归结果均在analysis/nas_followup_20261115/*.json。源数据copy-only，gzip level 1/mtime=0，两路CPU；两条固定主机密钥的SFTP连接，SSH banner等待120秒、元数据有界重试4次；32MiB边界复用已有前缀，完整NAS压缩字节SHA256及每个归档成员SHA256仍必须匹配。源文件未被替换；本地压缩暂存上限25GiB。

```bash
python3 -m py_compile yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py yestrack_diagnosis_20261101/analysis/nas_followup_20261115/nas_prefetch.py
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py run
# 仅在status=complete之后执行完成审计
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/audit_completion.py
```

上述run命令复用已完成回执和缓存，从未完成包续跑；当前49/58包通过，仍在传输，未声明全量完成。


### NAS 20261115 final closeout command (run only after migration complete)

Prepared finalizer verifies successful transfer and completion audit before publishing final receipts. It then captures latest project/analysis logs and control scripts, checking their NAS bytes. The command below is pending, not a completion claim.

```bash
cd /data2/user/LocateMOT_GroundJEV
python3 -m py_compile yestrack_diagnosis_20261101/analysis/nas_followup_20261115/audit_completion.py yestrack_diagnosis_20261101/analysis/nas_followup_20261115/finalize_transfer.py
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/audit_completion.py
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/finalize_transfer.py
```


### NAS 20261115 serial transport probe: connection-stage EOF

32 MiB single-handle SFTP probe failed before any payload write: NASClient -> Transport.connect -> start_client -> Packetizer.read_all raised EOFError. Therefore no streaming throughput conclusion and no change/restart of the live transfer. Probe target was never created. Existing session 30244 / wait cell 87 remains live; 49/58 packs have full NAS verification. No source results or model settings changed.

```bash
cd /data2/user/LocateMOT_GroundJEV
timeout 600s python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/serial_transport_probe.py
# exit 1: EOF during SSH key exchange, no upload; see serial_transport_probe.json
```


### NAS 20261115 18:13 UTC: terminal connection refusal and targeted repair

Transfer session 30244 / wait cell 87 exited 1 at 18:13 UTC: ConnectionRefusedError connecting 127.0.0.1:24558 during compact_03 upload. Subsequent direct TCP check found the same listener restored. Existing verified receipts remain 49 packs / 29,768 files; 3 local staged archives remain intact. Parent reconnectable() excluded this observed TCP refusal. The followup subclass now adds only ConnectionRefusedError to the existing bounded retry path, without editing the legacy transport. Failure status now distinguishes receipts obtained in this attempt from all locally recorded prior verified packs (the old zero count was per-attempt, not a loss of the 49 receipts). Official weights, inference, results, seeds and frozen payload membership are unchanged.

Prior serial-probe EOF JSON was preserved under its original UTC timestamp before rerunning. Regression: inject exactly one observed connection-refusal exception, then perform real NAS write/read/delete through the bounded reconnect path. A 32 MiB streaming diagnostic is also running; no throughput conclusion yet. Do not interpret test launch as success or start a duplicate main transfer.

```bash
cd /data2/user/LocateMOT_GroundJEV
python3 -m py_compile yestrack_diagnosis_20261101/analysis/nas_followup_20261115/nas_prefetch.py yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py
timeout 600s python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/serial_transport_probe.py
timeout 300s python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/refusal_recovery_probe.py
# Resume only after the targeted regression succeeds; old session has exited:
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py run
```


### NAS 20261115 refusal fix regression PASS and resume

Targeted refusal recovery passed: one injected refusal, 2 constructor attempts, 45-byte real NAS write/read/delete. Preserved prior diagnostic EOF artifact. Serial 32 MiB write/readback SHA256 passed; write 368.587 s (0.086818 MiB/s), readback 7.513 s (~4.259 MiB/s). Thus no evidence to change the parallel transfer algorithm; resumed existing frozen plan after the minimal retry fix. New main session 83968 / blocking wait cell 126; old session 30244 exited 1. Same 49 verified archives reused; 9 unfinished packs remain. No official inference, weights, seed, source results, or frozen payload membership changed.


### NAS 20261115 compact_03 readback corruption and contiguous-resume regression

Native NAS verification rejected compact_03 with zlib invalid stored block lengths; no acceptance criteria were changed. Local compressed SHA256 and all 557 local members passed the same verifier. CPU seed=2025 reproduction left a hole in range 1 while file length reached 5 MiB: old resume at 5 MiB produced wrong hash; new resume at contiguous acknowledged 1 MiB produced the expected hash. Both before FAIL and after PASS JSON are retained. Fix affects only transfer metadata, not official weights/inference/results. New upload checkpoints advance only after in-order range futures succeed; legacy unverified partials with no valid checkpoint cannot be trusted by length.

NAS corruption root pattern still awaits range comparison; do not claim all-zero holes until observed. Existing native session 83968 is shutting down after its recorded failure while other in-flight packs finish. Wait for its terminal handle before starting repair_uploaded_archive.py. Repair compares every compressed range to the fully validated local stage, changes only mismatched NAS ranges, then calls the exact native archive/member verifier and receipt path. Goal scope remains 58 packs / 36,305 files.

```bash
cd /data2/user/LocateMOT_GroundJEV
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/validate_staged_archive.py 04_groundjev_compact_03
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/out_of_order_resume_regression.py before
# Expected exit 1, preserved wrong-hash reproduction; after applying the fix:
python3 -m py_compile yestrack_diagnosis_20261101/analysis/nas_followup_20261115/nas_prefetch.py yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/out_of_order_resume_regression.py after
python3 -m py_compile yestrack_diagnosis_20261101/analysis/nas_followup_20261115/repair_uploaded_archive.py
# Pending: only once session 83968 exits; verified packs are left untouched:
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/repair_uploaded_archive.py 04_groundjev_compact_03
```


### NAS 20261115 actual all-zero resumed gap located

Old main session83968 is terminal exit1. compact_02 passed full native verification (1066 members), raising total to50 verified packs/30834 files. compact_04 was fully uploaded but has no receipt and remains untrusted. Started sequential repair command for compact_03/04, session57066 / wait cell139. Actual compact_03 compressed range at offset67108864 length33554432 was all zero; range134217728 length33554432 also differed. Both were rewritten from the fully validated local stage and immediately read back byte-equal. This confirms a real gap in the reused prefix, consistent with the CPU reproduction of unsafe file-length-based resume. The implementation error is in prior transfer recovery, not a change in research results. Native full archive/member verification remains required; do not count repaired chunks as completed archives.

```bash
cd /data2/user/LocateMOT_GroundJEV
python3 -m py_compile yestrack_diagnosis_20261101/analysis/nas_followup_20261115/repair_uploaded_archive.py yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/repair_uploaded_archive.py 04_groundjev_compact_03 04_groundjev_compact_04
```


### NAS 20261115 both corrupted copies recovered; resume final six packs

Both compact_03 and compact_04 now pass the exact native full archive SHA256 and member checks (557 and 710 source members). Each had three mismatched 32 MiB ranges; total192 MiB rewritten, including an all-zero64–96 MiB range in each NAS copy. Original source files were preserved. Total52 verified packs /32101 files /58601365524 source bytes. Repair session57066 /cell139 exited0. Authentic old NAS helper was frozen and published separately with SHA256 16219464d507238b7074c1b809572847e20f382c4605a728ab104ae4db203159 before replacing the main control code. CPU before_frozen reproduces the original expected FAIL with identical source/actual hashes and5 MiB unsafe resume; corrected code resumes at1 MiB and passes. Failure records retained. Resume remaining6 packs with contiguous-acknowledgement checkpoints; global58-pack audit and final log copy still pending.

```bash
cd /data2/user/LocateMOT_GroundJEV
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/capture_legacy_transport.py
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/out_of_order_resume_regression.py before_frozen
# Expected exit1 for authentic legacy fixture; JSON equals original before regression.
# Production code is the fixed helper, whose after regression passed.
python3 -u yestrack_diagnosis_20261101/analysis/nas_followup_20261115/migrate_research_evidence.py run
```


### NAS_RESEARCH_EVIDENCE_20261115_COMPLETE

补齐 36,305 个文件、100,702,571,726 源字节，58 个归档、35,431,013,859 NAS 字节。全部 NAS 归档及每个成员的 SHA256 回读通过，completion_audit.json=PASS；原始研究结果与权重保留。此前备份覆盖不足的判断已更正。
完成凭证：/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/nas_followup_20261115/completion_audit.json；NAS：/data2/user/nas/A800/research_evidence_20261115。


## A100 恢复验证（2026-11-20，不是新研究实验）

seed=2025；数据与权重留NAS，历史数值保持原样。

```bash
cd /data3/liuyeqiang/YesTrackV2
python3 recovery/restore.py
python3 recovery/configure_storage.py
python3 recovery/restore_r58_predictions.py
/data3/liuyeqiang/.venvs/fgrefmot-rmot-sports-20261019/bin/python recovery/verify.py > recovery/verification.log 2>&1
CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=2 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /data3/liuyeqiang/.venvs/fgrefmot-rmot-sports-20261019/bin/python recovery/gpu_smoke.py > recovery/gpu_smoke.log 2>&1
```

恢复证据见 ../../recovery/verification.json、source_files.json 和 r58_predictions_receipt.json。源码恢复脚本仅用于空的独立恢复目录；正常接续不应重复覆盖已恢复的源码或本机配置。


A100 单帧验证完成：GPU0、官方 V2 LoRA、两个候选，概率为0.96875与0.00860595703125，与原A800记录最大差0。模型与forward耗时10.43秒；包括NAS连续读取共411.78秒。匿名memfd内存传输避开初次FUSE mmap停滞，未在A100磁盘落地权重；临时目录已清理，验证进程正常退出。结果见 recovery/gpu_smoke.json。
