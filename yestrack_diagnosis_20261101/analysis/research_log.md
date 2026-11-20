# Research log

## 2026-11-01：复现前置检查

- 假设：单候选 crop 的 Yes/No 验证可能弱于关系、比较、无目标表达；TRP 可能在真值切换附近引入滞后。
- 已确认工作根目录与独立任务目录；官方源代码 commit 为 `ed42b8315b28c94dc595d83b0d49bf57002bb281`，未修改其模型或推理逻辑。
- 发现待核对差异：README 对发布 V2 adapter 建议 γ≈0.6，示例 TCP window=6/TRP Δ=4；论文为 γ=0.4/window=3/Δ=10。保留两种配置的区别，不静默调参。
- 本地已见 Qwen3-VL-2B 基座和 V2 原始数据，尚未取得官方 verifier adapter 和论文 tracker 候选。只做资源与协议检查，尚未启动推理、分类或探针。
- 保留：严格遵守复现门槛，任何未测指标写未运行，不给出推测收益。

## 2026-11-01：前置检查结果与暂停点

- R02 成功：val 库存 862 表达式 / 2,069 图像 / 1,990 标签文件，官方 split 为 0005/0011/0013/0019；原始表达式共 9,758。标签文件少于图像的语义待核对，不擅自补空或跳帧。
- 全部本地 59 个 adapter 配置中未发现官方 V2 命名或 Qwen3-VL-2B base 的 adapter；未发现 YesTrack ZIP。保留已有 OneJev 训练产物，但本任务不使用其替代官方 verifier。
- R03 成功验证公开提取码（errno=0），列出官方 yestrack.zip（178,142,422 字节），但匿名响应没有 dlink 或正常 sharedownload 的 sign/timestamp。第一可操作阻塞为资源文件不可取得；不能由此断言作者未发布权重。
- 修改：只增加 analysis/ 内的计划、冻结配置、两个只读检查脚本、检查 JSON、runs 与阻塞报告。官方权重/模型/推理逻辑未修改。
- 结果变化：尚无推理结果，HOTA/P/R/F1/ECE 均未测。暂停在步骤 0，未开展分类和探针，未申请 GPU；等待用户提供官方压缩包/资源绝对路径与 YesTrack-MOT 候选来源。

## 2026-11-01：扩大检索与官方 V2 资源恢复

- 用户指出服务器可能已有 V2，并授权检查现有百度网盘登录、必要时提供二维码。扩大磁盘文件名检索及压缩包中央目录检查后，找到服务器现有 BaiduPCS-Go 配置与客户端。网页会话接口 errno=-6，但 PCS 文件搜索成功，账号内已有 `/Yestrack/yestrack.zip`。上一轮只检查匿名分享页就停止过早。
- 使用原账号直接下载成功，无需二维码或更换登录。官方 ZIP 178,142,422 字节；CRC 检查通过，解压 4,092 个文件，共 361,534,107 字节。包含官方 V2 adapter、TempRMOT* 候选与 V2 GT；不包含单独 YesTrack-MOT 候选组。
- 准备输入时首轮读取 CSV 只取第一列，导致 19 个带逗号名称的行被截断。最小修复为使用官方评测器相同的逗号重组规则；重跑后 862 个完整名称唯一且全部与候选对应。未删样本，未改 seqmap 或 GT。共 1,850,576 条候选记录，MOT 1-based → image 0-based。
- 首次两候选真实运行检查在模型加载前失败：共用环境 Transformers 4.57.6 无法导入官方依赖 `Qwen3_5ForConditionalGeneration`。保留失败日志；建立任务局部独立环境，匹配官方 transformers=5.2.0、peft=0.18.1、torch=2.6.0+cu118 等依赖，不修改推理源码。
- 注册复现 GPU3/4（均在项目 allowlist）；预检查只使用 GPU3。原有任务保留，临时特征缓存未建立。

- 独立环境安装完成。补齐官方 einops=0.8.1 后实际两候选运行检查通过：adapter_loaded=true，Yes/No token ID=9454/2753，p=0.96875 / 0.00860595703125，峰值分配 4,436,303,360 字节。此处只有环境与权重连通性证据，没有 HOTA 或总体 referring 指标。保留失败日志与成功 JSON，下一步启动完整 862 项 TempRMOT* 复现。

## 2026-11-01：继续寻找 YesTrack-MOT

假设：缺少的候选可能在分支、发布附件或会议补充材料中。检查官方所有公开分支/提交/发布/tag/fork、作者仓库、issues/评论、HF 与会议论文补充材料。仅 main 一个提交，没有发布/fork；补充材料给出身份核验提示词与伪代码，但没有可核实的新资源链接。保留：官方资源库存和公开 API 快照。TempRMOT* 完整论文参数复现独立继续，尚未产生最终指标；不据此提前开展 A–H 分类或探针。检索脚本首次将 HTML 当 PDF 导致 pdftotext 失败，已按真实响应保存并重跑成功。

## 2026-11-01：GT tracks 输入准备

已写 `prepare_gt_candidates.py`，复用官方框解析器，后续须逐表达式与发布 GT 及原始 label 掩码核对；执行受完整复现通过标记约束。语法检查通过，尚未生成 GT 候选、分类或探针结果。公开 MOT 资源检索已完成，另把具体资源请求写成可审阅正文；是否向官方 GitHub 发帖已异步询问用户，未得到明确授权前不发送。原等待流长时间无新输出，做过一次最终 result.json 存在性检查，尚未生成，保留同一阻塞作业。

## 2026-11-01：完整复现未通过，停止下游

结果：官方 TempRMOT* 候选 + V2 LoRA，paper 配置 γ=0.4、TCP=3/0.4/0.3、TRP=10、video=4、seed=2025；TrackEval HOTA=40.132、DetA=30.520、AssA=53.190。相对论文差 −1.648/−2.170/−0.560，HOTA 超过用户 1.5 停止门槛。862 个任务、1,850,576 行输出完整，controller exit=0、within_tolerance=false。保留该结果，不改参数追分。

原因核对：官方 V2 训练权重公开且加载成功；发布说明存在 γ≈0.6 的校准差异。标注审计首次在 0019 尺寸断言失败，随后最小修改为完整记录差异并以 exit=2 报告，未改变接受条件或数据。0019 全部 1,059 张图像为 1238×374，发布 GT 为 1242×375。按发布坐标系重建的 491,286 个正例 object-frame 与本地标注全部一致，862 条表达式差异数 0。未能唯一归因 HOTA 差距；不能认定尺寸差异或校准单独解释了 1.648。

决策：按用户规则停止 GT referring、A–H 分类、误差分解、所有探针与错误图片；GT 输入准备脚本未运行。YesTrack-MOT 公开候选仍未找到，资源请求正文已备，未获授权对外发送。REPORT.md 与 runs.md 已更新为最终停止状态。

## 2026-11-01 第二轮授权

用户撤销 1.5 HOTA 自动停止规则：先 R13–R15 归因，再继续全部下游，统一“相对本地基线”。只用 TempRMOT*，放弃 YesTrack-MOT，原公开资源请求不再执行。基线仅按预指定 .6 是否胜过 .4 选择，不用敏感性扫描挑阈值。已阅读 γ 的评测过滤、推理连续分数输出、crop 坐标和训练负样本保留逻辑；先执行 CPU 归因，再估计并记录每个 GPU 阶段预算，>8h 询问。

2026-11-01 — YesTrack round 2: R13 shows precision rather than recall explains the paper gap (DetPr -13.596, DetRe +5.945 points). R14 fixed local gamma=.6 per the prespecified README rule: HOTA40.427 / DetA31.002 / AssA53.135, +.295 HOTA over .4. R15 measured max0019 crop shift4.123px; no coordinate correction. Complete candidate-preserving referring oracle reaches HOTA51.946 (+11.519), F-only oracle gain9.228, C .942, D .497; overlapping gains are not additive. H3 raw99.997; official integer-coordinate output alone lowers perfect-GT HOTA to97.720, a2.277-point confound in H3-H2, retained as a separate control. Frozen862-expression semantic review and100-row label_audit.csv completed; G has zero globally empty expressions, D21 paraphrases have only one GT-membership family. H2, paired context and V1 GT referring are running. User explicitly approved full2860484-row frame/video cache despite11.5–16h estimated four-GPU runtime; a single blocking owner queues it after earlier stages, with exact full-F TRP replay and all downstream deliveries prepared. All downstream results are relative to the gamma=.6 local TempRMOT baseline. No official inference code/weights changed.

2026-11-01 — R32 recovery: context, V1 and full-cache waiting-shell jobs returned143(SIGTERM), without model exception traces. H2 remains live. Evidence is consistent with external execution-session cleanup, but sender is unconfirmed. Preserved142/214 complete paired-context units and77/158 V1 units whose prediction rows plus all expected raw frame/video observations validate. Six otherwise complete V1 prediction units lack a complete gzip trace and are archived/recomputed; no sample is dropped. Resuming unfinished units under one shell owner with detached child sessions, fixedseed2025 and unchanged protocol. Full cache remains explicitly approved and queued.

2026-11-01 — Paired context probe complete (all107 C/D expressions and107 sequence-matched A controls;24 uniform frames/expression): D frame F146.946→55.446/60.142 at1.5x/2.5x crop; same-video A control gain1.927/1.550 points gives D differential6.572/11.645 points. C aggregate75.013→74.620/71.454 does not improve, but C_scene7 expressions/3 GT-membership families improve64.789→72.464 at1.5x. Full-frame320 degrades all groups. V1 full158 expressions/328330 candidates complete; source-selected gamma=.4, refine[.2,.8), F1=.787565976 frozen before target calibration. A targeted native replay check exposed1e-6 from np.round(.6203125,6)=.620312 versus official Python format=.620313; corrected offline serialization only, retained1e-12 criterion, then full V1 replay max difference0.0. H2 native owner recovery preserved648/862 complete expression/trace units and now runs detached; V1/context/queue were already detached and survive session cleanup. Full score cache approved and queued; expression work sharing addresses shared-GPU stragglers without changing sample batches. SoM two-frame single/multitoken true-forward pilot passed; final1704-frame stage will reuse the valid units.

2026-11-01 — Additional framewise-absence analysis (kept distinct from G globally empty expressions):816/862 expressions have empty-GT frames,237085/457503 expression-frames are empty. Local Temp gamma=.6 emits FP on62406 empty frames (26.32%),86077 positive candidate rows. Keeping all boxes/IDs and nonempty-frame scores, oracle suppression on only empty frames raises HOTA40.427→43.925, gain3.49777244 (DetA35.097, AssA55.456). This overlaps F gains and cannot be added. Saved30 actual-Temp empty-frame FP images undererrors/G_empty_frame_control with separate index; FN=0 by definition. Source V1 frozen gamma=.4/refine[.2,.8) transfers directly to existing actual-Temp V2 predictions: HOTA40.132 vs frozen gamma=.6 baseline40.427, loss.295; no new inference or target-grid selection. All figures remain relative to local baseline. Full H2 / score cache / TRP / SoM main stages still pending their complete receipts.

2026-11-01 — Full H2 completed:862 expressions/2860484 GT candidate rows; HOTA65.231987 /DetA48.203352 /AssA88.284481; referAcc83.7918%,P51.5889%,R91.3828%,F165.9478%. H2-H1=24.804525; H3raw-H2=34.765405; integer-box control gives semantic gap32.488. R19c split frame/video execution exactly matches827 original samples (344 video), maxdifference0.0; approved full cache has started. R29 manifest failed only on NumPy int64 JSON serialization after images/index were written; explicit int conversion and targeted strict-JSON regression retain all counts/seed/protocol. Resume unfinished CPU deliverable in detached completion owner; do not restart GPU inference.

2026-11-01 — R29 strict JSON fix complete:404 GT-candidate FP/FN images, all categories30+30 except D only14FN in population and G0. Reviewed seven category overview sheets, empty-frame supplement and selected full images; qualitative patterns saved error_patterns.md. R31 exact native H2 trace:421297FP,86.8544% finalp>=.99,58.4820% most recent unboosted frame/video decision belowgamma,16843 false threshold crossings on reused frames without a model call. Treat TCP amplification as an observed competing error source, not an estimated intervention gain. Full approved score cache runs independently; no inference/code/protocol changes.

2026-11-01 — R42 exact native trace confirms the saved A/FP01 mechanism:frame481 raw.1826171875, afterTCP.482617; frame482 reused score+.3=.782617, frame483=1.0 without new model calls. Prior3 final scores>=.4 at each boost. Two whole-expression replays exactly match native six-decimal output. Added trace.csv/result.json and report explanation; this is descriptive evidence, no heuristic intervention or inferred HOTA gain. Reproduction script includes the trace command.

2026-11-01T23:38:12 — R22 full frame pass complete:862 unique expressions/2860484rows,23225.396s(6.45h); video-only pass continues. Raw frame ECE=.0855314061,Brier=.0867570342,meanp=.257280663,positiveprior=.171749256;15 bins all overconfident. R45 full raw frame atgamma.6 P=.665974905/R=.762283069/F1=.710881933 versus H2 finalP=.515888574/R=.913828198/F1=.659478206:rawframe F1 +5.140373pts. Descriptive joint video/TCP/TRP contrast, not isolated TCP effect or measured HOTA gain. Per-sequence/calibration metrics saved, report/reproduction script updated. Remaining threshold transfer/video/TRP/SoM are still explicitly incomplete.

2026-11-01T23:42:02 — R27 calibration/threshold transfer complete:V1 and V2 each81configurations; both full native score replays maxdifference0. Source-selected(.4,.2,.8) F1=.787565976 onV1; onV2 F1=.650818992, -.865921pts versus fixedgamma.6 baseline. Target grid diagnostic best(.8,.2,.8) F1=.663450760, only+.397255pts versus baseline; source configuration1.263177pts below target diagnostic best. GT-track transfer HOTA64.918 (-.314); actualTemp transfer40.132(-.295). Both source/target best refine intervals unchanged [.2,.8); no claim that narrowing range helps. Main baseline remainsgamma.6; released runknown so prior correction skipped. Only approved full video/newborn cache and fullTRP/SoM remain.

2026-11-02T06:05:09 — R22 complete:46780.94355s(12.995h),862tasks/2860484GTrows; both phases862 unique assignments, selective video801329 actual samples. R26 newborn cache automatically started, unchanged4registered GPUs3,4,5,6 and1h prelogged estimate. R46 uses frozen0011 controls (D21, A51), whole GT candidate frame universe. D/A priors5.9175/15.3912%; rawframe TPR66.2775/82.9365%, FPR7.8650/5.0318%. Thus lower Dprecision is partly base rate, but raw conditional performance also worse in this single speed family; no generalization to all superlatives or independent-significance claim. Main gamma remains.6.

2026-11-02T06:30:55 — R26 newborn cache complete532Ftasks/28676rawframe/14060video samples in1512.701s. R28 all532Fexpressions/2150942GTrows:delta10native maxdifference0. Delta1/5/10/20 overallerror14.5522/17.8547/18.5803/19.1668%, F169.6555/66.0181/65.2107/64.2793%. Delta10-delta1 nearwindow+.673057pts,far+4.072951pts,DID-3.399895pts:do not support loss concentrated at GTswitches. Positivepriorsnear57.8512%,far18.5501%;28378nearunits vs2122564far. Truth1to0after0..5error82.1196%(delta1)vs90.5356%(delta10),+8.416pts;0to1after19.1385vs19.7380%,+.5995. Supports specific staleYes aftertruth-to-false but not attributing all F9.228HOTA oracle space toTRP. Main delta10/gamma.6 unchanged; SoM only remainingGPUstage, already running.

2026-11-02T07:32:01 — Main R25 SoM complete1704frames in3373.536s:orderedD crop/fullbinary/jointgamma F146.946/21.782/50.456, alwaysfirst71.264. Exactsingle-token D209frames F185.399 butalwaysfirst89.125. DpositiveGTalwaysindex1(100%); originalargmax selects1in76.587%frames. Cropconfusions exactly equalR23 originalD onall4908GTcandidates. Emptycontrol1200frames FAR23.833(crop)/8.833(fullbinary)/44.417(joint), not supportingnone benefit. R30 originalpipeline complete withupstreamgitdiffempty. New observed ordering confound justifies R47 pairednumber permutation onSAME1704units, seed2025+100000*seq+frame, no outcome-dependentselection/gammatuning. Inputmapping/croppair preservation checks passed for1704uniqueunits. SingleGPU6,1-2h estimatelogged beforelaunch (originalactual56min), detachedowner70543. Thisextra control remains pending; reportcompleteflagfalse untilitfinishes.

2026-11-02T08:23:41 — YesTrack diagnosis COMPLETE relative to localgamma.6 Temp baseline40.4274619. Fixed-candidate referring oracle51.9461961, gain11.5187342; F9.2280257, emptyGTframe rejection3.4977724(overlap), C.94165385,D.49664640. H2GT65.2319868; H3raw gap34.7654055 and integer-coordinate semantic control gap32.488. R47 same1704frames randomnumbering complete2910.874s:wholeanswer+newline D F117.1846(vsordered50.4559), showingstrongoutput/ordering sensitivity. Predeclared exactsingle-token N<=9 subgroup209Dframes:shuffleD F175.5556 vs crop60.9687/fullbinary33.8028/alwaysfirst26.5252; thuslimited joint-format benefit survivesfirstslotcontrol inthisspeedfamily. Matched969emptyGTframes FAR20.0206 vs crop18.5759/fullbinary6.7079%, no none rejection benefit. No extrapolation toallD/globalemptyqueries(G0), motionreasoning or HOTA gains fromsampleF1. R48 verified allcoverage,1704+1704units, exactcropprob/GTID/labelparity, native replays0,434errorimages,100auditrows, sourcecommit ed42b8315b28c94dc595d83b0d49bf57002bb281 unchanged. MaxFP32softmax normalization error1.8907e-7 (<1e-6). Officialweights/inference source untouched; allnewcode underanalysis. REPORT/runs/reproduce script/final receiptsupdated; allrequestedmainwork andadditionalorderingcontrol complete, optionalOneJevnotrun, unknownnegative-retentionr correction skippedperrule.

- 2026-11-02 YesTrack第三轮：先读官方TCP/TRP与现有R17/R22代码，已在analysis/plans/round3.json及runs.md预注册R49/R50。假设：最终分数回写历史和TRP缓存引起自锁；仅离线重放，V0逐值不一致即停止。V4固定T=1，以LOSO拟合b/stay/阈值≤3标量；固定版不调参。R51未经本轮批准不运行GPU。

- 2026-11-02 YesTrack R49/R50：V0全862/2860484逐值差0，HOTA65.2319868。CPU全部变体与LOSO完成，V4_fixed70.3790092(+5.1470224)，V4_LOSO70.2104977，V1+3.5070080，V2+2.1613129，V3+4.4893366。唯一失败为报告f-string字面量p未转义，已做最小模板修复，定向从已完成结果续写；不重跑、不改变预注册方案。R51参考R22估计8.4069h/4GPU，未启动，待用户批准。

- 2026-11-02 YesTrack第三轮CPU交付完成：R49全605个精确真→假事件；原始frame观察到跌破498个、均值3.498帧；native最终仅196个、均值6.296帧，配对延迟4.179帧，302/498仍删失；Delta1配对延迟2.154帧且153/498仍删失，锁存raw p在[.1,.6)比例67.42%/61.77%。支持TCP自反馈但不能排除video响应贡献。R50全部冻结变体均保留，固定HMM70.379009(+5.147022，oracle空间15.8428%)；LOSO校准70.210498(+4.978511)，无校准LOSO68.787015。固定HMM不是最快：切换后错误76.96% vs V3 66.53%；序列总体优势主要0019。REPORT_round3.md、主表/类别表/每折参数/曲线和数值收据完整；官方源码未改；GPU运行数0。R51全量实际Temp1850576条缓存估计4GPU 8.406861小时，严格待本轮用户批准，不挪用第二轮授权。保留实验结论与完整已完成CPU输出；报告格式错误已最小修复并定向续跑。

- 2026-11-02 YesTrack R52用户续补：先做推理预算对齐；旧R50 V0/V1/V2用Delta10，V3/V4/V5用Delta1。冻结新的两项Delta10 HMM对照，原R50集合不改；只读R17原生实际观测，中间帧只转移，固定版及训练三序列LOSO≤3标量。用户已条件授权：若Delta10 HMM>=+2且估时<8h，实际Temp仅跑Delta10原生带trace一次；否则询问全帧缓存，当前不启动GPU。

- 2026-11-02 YesTrack R52 CPU补查完成：Delta10固定+3.001451，LOSO+4.250096且4序列均正；全部2538137中间行仅转移误差0，V0仍差0。按用户条件授权进入R53：实际Temp仅原生Delta10 trace一次，冻结实际CPU比较集合5项，直接转移R52训练折参数、不拟合实际候选；GPU5/7两张，启动前估时7.172h(参考R09并用R22共享卡实测最慢阶段放大3.247倍)，<8h，完整逐帧缓存不运行。

- 2026-11-02 YesTrack R53预算修正：启动前7.172h估计偏低；实际25.17min/47条，减120s初始化后工作量代理外推12.691–14.811h，已超用户<8h自动运行条件。仅暂停PID[200596, 200598, 200655, 200656]，状态T逐一核实；其他用户任务不动；完成数据/内存/trace保留，模型显存仍占用。未完成原生全量，不汇报部分HOTA，不跑全帧缓存。CPU R52两HMM+3.001/+4.250及所有四序列/机制检查交付完整；新预算继续需用户决定。

- 2026-11-02 YesTrack新指令：R53开TCP旧run不续跑，4PID已按SIGINT/finally关闭trace后退出并释放GPU。代码确认video路由依据本次fresh frame p且在TCP之前(945–949 vs1004–1017)；reuse旧分数不参加路由(892/944)。新增R54单标量γ-LOSO已预注册，同HMM训练micro-F1目标与9点阈值网格；先CPU。另发现上次预算漏计rank1：官方1184行仅rank0打印OK，暂停时实际89完整文件，均mtime早于pause，原47及12.7–14.8h估计需更正。后续GPU按用户要求只跑官方noTCP一次，等低负载且估时<8h自动启动，不再问权限。

- 2026-11-02 R54完成：V1 γ-LOSO68.034903(γ=.6/.6/.6/.7)，对固定68.738995为-.704092；HMM69.482083高1.447180(原固定gap.743088)。单阈值控制未解释优势，但差异主要0019且0013 HMM低1.416，不声称独立滤波普适显著。代码route在TCP之前、只freshindices。旧预算错误首因已找到：1184只rank0打印OK；暂停时89完整输出，旧47/12.7–14.8外推作废，修正6.718–7.837；旧run按用户取消，不续跑，4PID退出、显存释放，trace闭合完整。新noTCP实际CV计划已冻结，实际3训练序列fit b/stay/τ≤3，等待低负载自动启动。

- 2026-11-02 R55低负载队列owner270415已建立，尚不请求新授权。原生科学参数比R09仅去stability_enable，CUDA物理资源由队列连续3次现场准入选择，总项目≤4。实际HMM的LOSO按完整视频留出，在实际训练三视频固定R20候选标签上拟合b/stay/τ≤3；与GT三视频拟合结果分列。R54四折2860484判定逐值核对通过，1参数、无全val调参。后续单条阻塞wait，内部资源/进度检查，全rank完整文件计数。

### YesTrack R55 NCCL同步失败与恢复（2026-11-02）

首轮原生noTCP在2.526小时、760份完整预测后退出；首个错误为快rank0在末尾collective等待慢rank1超过600s。752个查询同时满足完整trace/几何/原生六位逐值差0，予以保留；8个完整预测缺trace，和102个未完成查询共110个完整重跑。只在analysis外层延长NCCL同步timeout到8h，官方源码/权重/seed/三个变体不变。初次CPU恢复脚本的manifest排序假设触发assert，已改为官方seq/expr排序并复核通过。接下来重新等待低负载、启动前登记剩余及总预算，官方--resume。保留失败记录，不丢样本。

### YesTrack R55-complete（2026-11-02）

实际候选全量862表达式、1850576行完成。原生V1去TCP 41.211111 HOTA，相对R14 +0.783649；固定HMM 41.087281、LOSO HMM 40.149440，均未超过V1，LOSO四序列相对V1均下降。GT候选HMM收益未直接转化为实际收益。新原生V1逐值差0，三版输出/缓存一致、LOSO整序列隔离≤3标量、未观测行仅转移；8条因trace不完整重跑的预测与原预测也差0。累计GPU原生5.137h，未跑全帧缓存。保留原NCCL失败和CPU排序修正记录；只延长同步timeout，不改官方权重/推理逻辑/seed。结果及命令见任务analysis/REPORT_round3.md、runs.md。

### YesTrack R56 研究计划（2026-11-04）

假设：原R20固定候选11.52 HOTA空间可能有部分来自未匹配候选，不全是语言语义错误。先只读R14/R20和发布字段；全862文件9列、7–9列恒1，无可用检测confidence。冻结两个部分oracle、固定L10/A400和按整视频LOSO拟合两个阈值的表达式无关过滤；用官方HOTA评估并分开净规则收益与垃圾命中oracle。HOTA非加性，报告先垃圾后语义分账与交互，不把规则未恢复空间当成必须看图的证明。只用CPU，新产物放R56，不改旧结果。

### YesTrack R56-complete（2026-11-04）

R14正候选496433：R20 TP259690、语义FP179889、未匹配垃圾FP56854；语义FN23296。清垃圾HOTA41.802012（+1.374550），纠语义含FN49.490162（+9.062700），全oracle51.946196，交互+1.081484。先垃圾后语义分账1.374550/10.144184，对称归因1.915292/9.603442。仅tracker元数据L/A，confidence列恒1不可用；固定规则HOTA40.555148，整视频LOSO40.510874（+0.083412，清垃圾空间的6.07%）。LOSO删除TP3733、语义FP2924、垃圾FP5751；仅垃圾命中诊断+0.162175（11.80%），尚余1.212375垃圾空间未被该规则覆盖，不能据此证明必须看图。全CPU104次独立逐视频网格评测及40别名复用，未用完整val选阈值；144个训练目标重算、5个输出每行与定义一致、官方源码不变。仅新增R56目录及独立报告，原结果不改；保留该诊断，不扩网格/变体。

2026-11-04 R58：检验属性概率校准及乘积/多帧校准；只用 V2 train，seed2025。CPU 数据审阅找到本地 KITTI 原始 labels ZIP，V2 轨迹 ID 不同，按逐帧 Hungarian IoU>=.5 对齐。首轮准备错误把 V2 左上角当中心，已按官方 parser 修正并保留失败草稿，尚未推理。用户修订为单取值一对多二值标签与静态一致性排除；当前2065图像/536轨迹，主表仅类别与车辆颜色，衣着等留附表。完整定义在 analysis/plans/r58.json 冻结后才启动200样本/模型吞吐试跑，预算>4h等待批准。保留原实验所有结果和原模型/推理源码。

2026-11-04 R58开跑前修正：在零模型推理/零分数缓存时发现正例被同类域条件额外排除，停止等待权重的owner，保留旧草稿和图。改为所有可见E_v GT直接正例，独立同类/衣物/性别条件仅用于负例，按用户定义重新冻结2144帧/540轨迹。独立源GT正例检查17992次、遗漏0、源标签帧/真值错配0；采样与已知Brier/AUROC、合成温度检查通过。用户最新判定是等样本量二值ECE主判/等宽交叉冲突=部分成立，Brier分解/NLL诊断不作门槛。按官方依赖在独立overlay补齐einops/OpenCV/FLA0.5.2，旧环境不动；仍只授权200样本吞吐试跑，全量>4GPU小时须审批。

2026-11-04 R58：HTTP权重下载超时，发现本地原始Qwen2检查点与冻结revision完全一致；复用原文件并优先试跑，不改变科学定义。其余模型继续同revision下载，完整预算仍待吞吐测量。

2026-11-04 R58：按用户修订固定二值一对多标签、等样本量15箱主判/等宽交叉核对，NLL/Brier分解仅诊断。冻结样本2144帧/540轨迹，主属性类别及车色；其它属性样本不足单列。六个模型250请求/模型的试跑均完成，共1500请求/25500题，种子2025及revision/概率完整性检查通过。Perplexity精确官方运行时torch2.14 CUDA13因驱动12080不可用，记录跳过。权重使用同发布者ModelScope传输并对冻结HF SHA256核验；原YesTrack和qev源码diff为空。Qwen共享前缀不满足冻结.005容差，继续完整选项打分；已有概率保留。先前前台终端SIGTERM由独立进程组恢复，不重跑已完单元。完整实测外推44.325 GPU阶段小时，试跑已用0.949，剩余43.377；超过用户4小时上限，未启动正式全量，等待预算批准。当前P1–P6假设未判定；保留完整冻结方案。

2026-11-04 R58：用户明确批准剩余约43.4 GPU小时的全部冻结实验。启动六模型全量，按mini/flash/OneJev/Qwen2/Qwen8/turbo优先顺序执行；完整缓存后接CPU分析，不改指标/样本/seed或原有结果。

R58：为缩短报告关键路径，增加完整单模型缓存上的原定CPU分析入口，与后续GPU阶段重叠；末尾汇总复用成功单元。未改变任何科学定义或原始分数。GPU推理仍按冻结顺序串行。

2026-11-05 R58 d3-mini完整结果（保留；其余模型继续）：检验“全局单T足以校准并允许乘积/多帧”的前提。GPU全量实际2.474h，6×2144缓存完整；原定两套CPU分析全部成功。主属性宏ECE原始0.061373、全局T-LOSO后0.062052；类别0.018118通过，车色0.105986未通过；T变异系数0.013685稳定。P5乘积ECE0.162916，直接问0.108904；乘积减直接NLL=0.107983，轨迹95%CI[0.044733,0.169175]。P6固定均值规则K4同队列准确率0.821284→0.890378，但ECE0.068668仍>.05。按冻结标准该模型“部分成立”，两取值敏感性结论相同。原子车色概率已失校准，不能只由乘积失败归因为属性依赖。全部模型对照、自动噪声参考仍等其余五模型完整结果，不改方案。

2026-11-05 R58 d3-mini分组诊断（原冻结计算，保留）：车色全局T ECE随框高<40/40–100/>100分别0.169861/0.068754/0.047644，对应等宽0.170131/0.070245/0.051934；大框末项跨分箱有差异，不能只凭等量数值称完全达标。P4总体翻转率0.078196，但性别/下装探索性属性分别0.307049/0.379845。P5共有178个不同属性-取值正确性相关对，其中64个phi有定义；样本最多的Car×black为0.069470，轨迹CI[-0.009882,0.144730]，该项不足以单独说明依赖，乘积失校准同时伴随车色原子概率偏差。补全既定诊断的全模型CSV呈现，未新增实验、阈值或判定门槛。

2026-11-05 R58：发现Qwen全量重启会重新以首个未缓存样本做KV缓存门槛，与冻结的first-pilot定义不符；在Qwen全量启动前修正为继承原pilot失败状态。两个模型CPU控制流回归通过，均固定fresh full-option；未产生任何受影响的full概率，pilot保留。原预算和科学定义不变。

2026-11-05 R58 d3-flash（保留）：GPU全量3.267h，6×2144缓存完整；主/严格两套CPU分析成功。缓存核对一度因Path.resolve把venv符号链接解析到裸解释器导致缺NumPy，保留失败命令并仅修正解释器入口，目标核对通过；CPUowner使用原正确venv路径。主宏ECE原始0.058892→全局T后0.058993（噪声0.007893）；类别0.021618通过、车色0.096368未通过（噪声0.013074）；T CV0.016435稳定，措辞翻转0.069412。P5乘积ECE0.157861（噪声0.016527）/直接0.099154（噪声0.021547），乘积减直接NLL0.122955，轨迹95%CI[0.064831,0.186861]。K4固定均值规则准确率0.812993→0.909955，ECE0.066109（噪声0.026271）仍未达标。主/严格均“部分成立”；严格P5只有1799二元、0三元，不能据整体相同声称三元也稳健。继续OneJev及两组Qwen/turbo，未改冻结方案。

2026-11-05 R58 OneJev1.5-9B（保留）：GPU0.942h，6×2144缓存核对通过，主2144样本/19490二值记录及严格2111/19016均CPU成功。原始主宏ECE0.061729，全局T后0.060205（噪声0.008384）；类别0.028239通过，车色0.092170未通过（噪声0.013353）；T CV0.018163稳定。主措辞翻转0.104706（CI[0.094574,0.114179]）按冻结点估计10%门槛未通过；严格版本该项通过，整体均因只有部分属性达标判“部分成立”。P5乘积ECE0.179193（噪声0.016475）/直接0.146267（噪声0.021022），NLL乘积减直接0.027202，CI[-0.049282,0.099136]，不能声称直接NLL明确优于乘积；乘积AUROC0.811572高于直接0.792347。K4固定均值准确率0.806800→0.893703，但ECE0.073878（噪声0.028168）未达标。Qwen2全量已按既有失败pilot门槛走fresh，继续完成两组Qwen及turbo；未改定义。

2026-11-05 R58：Qwen2B main全量已齐，先执行与其它设置无依赖的既定CPU计算，措辞/crop后补；主分数/标签/轨迹等逐值检查后恢复OOF结果，模型完整标志保持等待。真实d3-mini检查点重放误差0，Qwen2 main 2144/19490完整。只是调度与恢复单元拆分，未改科学定义或GPU逻辑；先前完整模型结果保留。

2026-11-05 R58 Qwen3-VL-2B主配置CPU检查点（保留，P4/crop尚未完成，不计完整模型）：2144样本/19490二值记录，主/严格两套既定核心分析成功。全局T均值3.155383、范围3.003410–3.218915、CV0.016586；原始主宏ECE0.078995，LOSO单T后等量/等宽0.024915/0.026279（完美校准有限样本噪声0.009586），类别0.005301/0.006744，车色0.044529/0.045815，均通过对应P2门槛。P5乘积ECE0.085252（噪声0.022425）仍>.05，直接问0.157817；乘积减直接NLL=-0.032301，轨迹CI[-0.082091,0.020013]，差异不明确。固定均值log-odds K2同队列准确率0.849582→0.878789，ECE0.045430/0.047609，满足固定P6子项。P2单属性校准并非决策模型独有；不能据此声称完整P1–P6通过，也不能将P5失败单独归因为独立性，因探索性属性和组合子队列仍可能失校准。严格版主宏0.021941、类别0.005111、车色0.038771。报告增加明确标注的main-only表，全部标准/样本/既有数字不变。

2026-11-05 R58 Qwen3-VL-2B完整模型（保留）：GPU全量10.841h，6×2144缓存/19490二值记录核对通过；main OOF输入逐值核对后复用，P4/crop主/严格两套补齐，正常completion均true。主P4措辞JS0.048686，翻转0.154824（轨迹CI[0.142959,0.166631]）及排序翻转0.166181，未过冻结10%措辞门槛；P5乘积ECE0.085252未过，P2全局T及主属性、T稳定性和P6固定K2均值通过，完整判定“不成立”（严格版相同）。对照说明单属性温度校准不是决策模型独有，但该Qwen未通过整套组合/措辞标准，不能称完整前提成立。crop主宏ECE0.037422/0.038573，高于双图0.024915/0.026279；按既定同一T评估。已查看车色和P5可靠性图，图表可读。Qwen8沿原流程接续。

2026-11-05 R58 Qwen8执行瓶颈（保留全部有效缓存）：物理GPU6与另一任务共享计算，前140请求25.44秒/条而pilot在GPU3约6.97秒/条。一次性能诊断确认共享负载，未操作其它任务。analysis资源选择改为在允许清单/显存/项目≤4GPU约束内优先较低利用率，CPU选择回归通过。仅本任务pipeline2090465/owner2090466/worker3132489经路径和命令核实后退出；367条main及其余5配置各10条均为完整无重复JSONL，零删除/重写。旧进程耗时4280.52秒另存resource_handoff_Qwen8.json计入最终运行成本；原pipeline重启从未完成单元恢复，新pipeline3217225。冻结plan、权重、seed、推理接口与判定未变，恢复速度待实际请求日志确认。Qwen2与既有4个完整模型结果不重跑。

2026-11-05 R58 Qwen3-VL-8B全量main核心CPU（保留，P4/crop待齐）：2144/19490与严格2111/19016两套成功，bootstrap1000/seed2025；尚不计完整模型。主原始宏ECE0.108277、全局T后0.065322（等宽0.065281，MC噪声0.009334）；类别0.022128通过，车色0.108516/0.107596未达.05。T均值6.409253/CV0.014010。P5乘积ECE0.192733（噪声0.017590）/直接0.100207（噪声0.026124），NLL乘积减直接0.255891，轨迹CI[0.173220,0.341892]。K4固定均值同队列准确率0.801886→0.860174，但ECE0.099450/0.093934不达标；K2/K8固定规则亦不达标。严格版主宏0.060556/车色0.103241，P5乘积0.169301，保留全部预定结果。GPU继续wording/order/crop，完整判定等P4；不因模型较大而假定优于Qwen2。

R58 Qwen3-VL-8B完整模型（保留）：GPU恢复阶段97108.258秒，加共享GPU6中断前4280.520秒，全量28.164h，pilot另计；6×2144缓存完整，main输入逐值核对后主/严格两套CPU补齐。P4措辞JS0.036126、翻转0.193020（轨迹CI[0.180188,0.205746]）、排序0.098761；正式措辞门槛未过。P2类别通过而车色不通过，T稳定，P5乘积和P6固定规则均不通过，按冻结“只有部分属性满足”定义为部分成立，严格版相同。该标签不代表比Qwen2更好；单属性概率基准仍应比较实际ECE及稳定性。Qwen8 crop主宏ECE0.082102/0.081821，双图0.065322/0.065281。P3预定条件诊断：Qwen2车色整体ECE0.044529，但小框<40像素N1474为0.075257（噪声0.027680），40–100为0.046701、>100为0.038014；汇总通过不能代表各条件都校准。Qwen8对应0.169623/0.080642/0.048569。Turbo沿冻结计划继续GPU。

R58全量研究完成（保留全部结果）：六个可运行模型均完成6×2144缓存、主19490/严格19016二值记录的两套CPU P1–P6、17序列LOSO、1000轨迹bootstrap及全部预定消融/效用。正式缓存共77184请求/1312128题；不读val、不用YesTrack LoRA。最终完整性检查通过，派生缓存0.653GiB<25GiB，官方YesTrack/OneJev子仓库diff HEAD为空。GPU阶段实测48.815h（含pilot及Qwen8迁移前1.189h），高于44.325h外推，原因是共享负载，正式样本/题库/设置未增删。

R58结论：0/6通过整套冻结标准。四决策模型均只有部分属性成立；Qwen8同样部分成立；Qwen2虽在主属性单T（宏ECE0.024915，噪声0.009586；类别0.005301/车色0.044529）、T稳定及固定K2多帧达标，但措辞翻转0.154824和乘积ECE0.085252（噪声0.022425）未达，整体不成立。决策组主宏/乘积ECE最低均为d3-turbo：0.054931（噪声0.007825）/0.136500（噪声0.017534），均未过；措辞翻转0.067216达标。Turbo减Qwen2的P4翻转差-0.087608，配对CI[-0.1005,-0.0754]；P5乘积ECE差+0.051248，CI[0.0315,0.0663]，校准并非决策模型独有优势。Qwen2最大Car∧black组合N1387，乘积ECE0.084697，轨迹CI[0.062187,0.119140]仍>.05；不能将整体失败只归于衣着小样本，也不能单独证明条件独立失效。当前标签噪声参考：六模型一致反向车色9.58%/性别34.85%，只是自动复核线索，693张审计图和50条表达式审计已导出，人工列仍空，未改标签。最终REPORT_R58.md保留所有原定数值/噪声/CI/图与LOSO阈值，结论限于现有标注；停止新增推理，目标交付完成。

2026-11-12 NAS迁移准备（只读盘点）：确认项目根GroundJEV；统计两个工作树、外置LocateMOT-checkpoints/LocateMOT-runs及R58模型/预测缓存，剔除原始数据和可重建环境。按inode去重、记录符号链接真实依赖，区分训练权重/恢复状态/发布模型/代码/实验结果；先统计，不复制或清理，不跑GPU。新脚本和清单放analysis/nas_inventory_20261112/，计划先落盘再单次阻塞扫描。

2026-11-12 NAS盘点完成（保留）：175774物理文件，849.360 GiB；代码/配置/文档0.1775、Git0.4826、项目权重400.3770、训练恢复193.2942、发布基础模型125.4286、实验结果98.7337、派生训练/特征29.9656、下载临时0.9003 GiB。排除原始数据和可重建环境；inode去重，不做内容hash，不加载tensor、不迁移删除。外部/data3与R58依赖已纳入；逐文件清单和checkpoint组清单生成。元数据汇总首轮因Path.parents开销中断，等价前缀优化与针对性检查后重放initial快照成功；无实验结果更改。容量/行数/物理来源/权重分组加和核对通过，断链/读取错误均0。报告：yestrack_diagnosis_20261101/analysis/nas_inventory_20261112/REPORT.md。

2026-11-12 checkpoint重要性审计开始：基于NAS已有元数据，先读导出/merge代码及训练回执，按正式终点、研究对照、当前依赖和可恢复性筛选；旧文档状态与实际回执交叉核对。仅生成优先保留/暂缓/待确认清单，不删文件、不迁移、不改模型。新输出analysis/nas_inventory_20261112/checkpoint_audit/。

2026-11-12 checkpoint重要性审计完成（仅建议，不删不迁移）：原清单382项项目权重加恢复状态/发布模型配套共1034项719.100GiB；优先172项51.865GiB，另配套237文件，总精简清单409文件/52.683GiB；暂缓855项649.875GiB；待确认7项17.361GiB。项目权重保留34.423GiB，覆盖G2正式18227/耦合11000-17000-17500/中期portable、OneJev500/native-teacher600/broader6000/history成对对照/8227LoRA及准确native600底座、旧U1U2/官方YesTrack LoRA和小型研究头。大型工程探针、中间全模型、非优先Adam备份、可再导出的包及可重下载公开大模型暂缓；旧G1 delta两工作树均缺失、未完成旧课程等单列待确认。保留一个G2终点和0.12GiB8227恢复备份；没有把BF16权重等同FP32/Adam恢复。暂缓完整导出依赖闭合、选中config/存在性/大小/inode/容量核对通过，未重载tensor/未做推理或全量内容hash；原inventory/实验结果不改。详情analysis/nas_inventory_20261112/checkpoint_audit/REPORT.md和migration_keep_files.csv。

2026-11-12 用户批准移动已审计精选checkpoint。NAS A800已挂载可写，可用约3.3TiB；独立目标/data2/user/nas/A800/selected_checkpoints/LocateMOT_20261112/，不触碰正在运行的全盘_migration_control备份。仅409文件/56567703095字节；CPU双文件并发复制、完整SHA256读回核验后，将原文件和本项目范围内已识别硬链接别名原子替换为NAS符号链接，保持原路径可用。先冻结逐文件plan和别名，逐单元保存verified/completed，可从未完成单元恢复；不迁移暂缓/待确认独立权重，不改权重内容、不改官方推理逻辑，不用GPU。

2026-11-12 用户明确授权“NAS任务接手”。已向现有NAS任务“核查 NAS 文件路径与大小”（01a12b7b-30ad-7ff2-a097-fb1f65f76c0f，nas57）发送精确409文件/56567703095字节、SHA256和两批files0清单。NAS通过已有只读rsync直连拉取，在独立selected_checkpoints/LocateMOT_20261112目录逐文件本地校验并写回执；不得修改全盘备份或A800原文件。A800在完整回执核对后才原子切换458原路径。源端SHA256计算45.47秒；home临时配套11文件/1132字节。没有重启慢速SFTP完整传输。

2026-11-12 NAS精选迁移交接完成、传输尚在进行：NAS两批小型dry-run通过，独立rsync任务已启动。A800最终等待/切换服务locatemot-selected-ckpt-finalize-20261112.service已验证ActiveState=active/SubState=running（MainPID2809170）。仅旧等待器2658139被停止，NAS拉取和原有全盘备份未中断；全部源在NAS校验通过前保留。NAS任务已收到补充要求：等待A800最终status.json=complete，复核migration_receipt409行与source_aliases458行后才视为全流程交付。当前不宣称迁移已完成；最终回执由服务写入本地transfer_20261112与NAS独立目标目录。全过程不使用GPU、不改模型内容。
2026-11-12 checkpoint迁移监控目标保持active：NAS四路分片传输运行中，A800 finalizer service active。建立单次阻塞监控器，直到409文件NAS SHA256校验完成并完成458路径切换，失败则停止并定位首个错误；不扩大清单、不重启全盘备份。
2026-11-12 迁移监控故障：NAS_PULL status 在第3次冻结分片重试后为 failed；日志首个可操作原因是到 `124.115.123.132:22224` `Network is unreachable`，并行 rsync `[12,12,255,255]`。NAS `source_files_modified=false`，409文件范围和目标未改变。A800 finalizer 因NAS状态读失败退出；恢复网络/传输后再继续最终SHA256与458别名切换审计。

2026-11-13 恢复审计第1轮：重新核对NAS状态仍为 `failed/copying`（attempt=3，verified=0/409），源端 `124.115.123.132:22224` 已可达；A800 finalizer 仍为 failed。按用户已授权的原NAS任务发送冻结清单断点恢复请求，但跨任务控制端请求超时，本机 `127.0.0.1:2439` 无监听；未创建新任务、未扩大清单、未修改源文件或原路径。

2026-11-13 恢复审计第2轮：NAS状态、A800 finalizer 和源端可达性与第1轮相同（failed、verified=0/409、finalizer failed、source 22224 reachable），跨任务控制端 `127.0.0.1:2439` 仍不可用；未重复发送恢复命令，未创建新任务或修改迁移范围。

2026-11-13 恢复审计第3轮：NAS仍为 `failed/copying`（attempt=3，verified=0/409），A800 finalizer 仍失败，源端可达但跨任务控制端 `127.0.0.1:2439` 仍无监听；三轮恢复审计未发现外部状态变化，按门槛停止继续轮询。

2026-11-13 新阻塞审计周期第1轮：goal恢复后重新核对，NAS仍为 `failed/copying`（attempt=3，verified=0/409），A800 finalizer failed，源端22224可达但 `127.0.0.1:2439` 无监听；未执行重启或新建迁移任务。

2026-11-13 新阻塞审计周期第2轮：NAS状态文件未更新，仍为 `failed/copying`（attempt=3，verified=0/409），A800 finalizer failed，源端22224可达但 `127.0.0.1:2439` 无监听；未重复发送恢复命令。

2026-11-13 新阻塞审计周期第3轮：NAS状态文件仍未更新（failed/copying，attempt=3，verified=0/409），A800 finalizer failed，源端22224可达但 `127.0.0.1:2439` 无监听；连续三轮无变化，按门槛停止本周期监控。

2026-11-13 修复迁移通道：确认失败原因是 NAS 端反向 rsync 到 `124.115.123.132:22224` 的路由不可达；同机 SSHFS/SFTP 写端 `127.0.0.1:24558` 可用，既有并行 SFTP 试跑已成功。新增 `yestrack_diagnosis_20261101/analysis/nas_inventory_20261112/checkpoint_audit/run_sftp_fallback.py`，只复用冻结409文件/56567703095字节 plan，调用既有 SFTP worker 做远端读回 SHA256，再桥接原 finalizer 的 nas_pull_verified/status 接口；不改官方权重、源文件或迁移范围。2 MiB 上传/读回/删除烟雾测试通过。预估按已测1.57 MiB/s约9.5小时，正式任务启动后使用单一阻塞命令等待。

2026-11-13 SFTP fallback 已启动：唯一长任务 `run_sftp_fallback.py`（会调用 `transfer_to_nas.py`、再桥接回执并调用原 finalizer），固定409文件/56567703095字节；启动后约264秒已上传1.281 GiB，无错误，0个文件尚未完成读回校验。原NAS反向rsync不再重启。

2026-11-13 migration recovery: the pinned SFTP fallback completed and verified the first two 9.022-GiB files (2/409; 18.044 GiB), then failed while writing the third file because a Paramiko worker connection timed out and the NAS SFTP endpoint dropped it (`SSHException: Server connection dropped`, after `PipeTimeout` in `write_range`). The third destination remained only as a 250,085,376-byte `.partial`; no destination final file or source modification occurred. Added bounded reconnect/retry (up to four attempts) for create/write/read worker operations, discarding the broken thread-local client before retry; `py_compile` passed and the existing 156,389,221-byte parallel SFTP pilot passed (upload 26.85s, readback 15.86s, SHA256 matched, source unchanged). Resume from `verified.jsonl`/`completed.jsonl` without changing the frozen 409-file scope.

2026-11-13 recovery continuation: the second SFTP resume was externally SIGTERM'd around 1.47 GiB into file 3; `verified.jsonl` and `completed.jsonl` remained at exactly 2 rows, and no final destination or source alias was changed. Added a detached supervisor that starts the approved wrapper in a new session and records `supervisor_status.json`, so a terminal/session timeout cannot terminate the transfer. The frozen scope remains 409 files / 56,567,703,095 bytes / 458 aliases.

- 2026-11-13 NAS completion audit initially found 4 extra `.rsync-partial/model.safetensors` files under the selected destination. They were stale remnants of the earlier failed reverse-rsync route, absent from the frozen 409-file plan and all receipts. Removed only those four partial files and their now-empty `.rsync-partial` directories; migration payload and 409 verified files were unchanged. Re-run the full audit.

- 2026-11-13 migration completion audit passed after removing the four stale `.rsync-partial` remnants: 409 frozen units, 56,567,703,095 bytes, 409 NAS payload files, 409 verified/completed/receipt rows, 458 alias rows and 458 source symlinks all match; no partial/temp files remain; NAS status and supervisor both report complete with zero errors and `source_files_modified=false`. Goal completion evidence is now sufficient.

2026-11-13 补充重要文件迁移审计：已完成精选409文件迁移后，重新检查checkpoint_audit/review_files.csv。确认7个待确认主权重无法由现有delta/正式终点替代，合计17.361GiB；连同同目录配置、tokenizer和回执等上下文共63个归档路径、约17.469GiB。用户授权“有的话继续传输”，本轮单独写入supplemental_transfer_20261113：7个主权重验证后原子替换为NAS符号链接，31个普通配套文件和25个已解析上下文路径只复制、不改源。预计按既有1.6MiB/s保守约3.2小时，实际以NAS挂载吞吐为准；不扩大到849GiB清单，不迁移数据集或可重建环境。

2026-11-13 代码快照迁移：盘点中的代码/配置/文档/Git类别共14961个文件、0.660GiB，其中5个临时Git pack（约0.097GiB）排除，冻结复制范围14956个文件、约0.564GiB。生成copy-only tar快照到NAS project_snapshot_20261113，逐源文件SHA256清单与归档SHA256并列保存；不替换任何代码路径，不搬数据集、环境或实验预测缓存。

2026-11-13 分析证据迁移计划：R49–R58分析目录中非模型代码/结果/报告/日志/分数缓存/图像共108652个物理文件、约5.385GiB。6个已进入主checkpoint归档的published-model符号链接排除；冻结copy-only tar快照analysis_snapshot_20261113，源分析文件不替换。

2026-11-14 补充迁移完成并审计：7个待确认主权重及56个上下文共63路径、18,757,425,437字节已完成全量SHA256读回；7个主权重原子切换为NAS符号链接。代码/Git copy-only快照14956文件、605,122,665源字节完成；分析证据copy-only快照108652文件、5,782,448,332源字节完成。代码归档SHA256=260840c56e07cd9908e02ee437a6ddcfbaf5ab6dff1597f0685ed54321763b2f，分析归档SHA256=8fc06f8857f1d50dba20dad8e011e5ea7d0f3c3e068591b4a05f0bce1189e572；源代码和分析文件未修改，目标无.partial/.tmp。剩余为原审计暂缓的可重下载模型、非优先恢复状态、过程探针/可重建缓存和原始数据。

2026-11-14 增量迁移审计：GroundJEV根目录及四个NAS状态均正常；主迁移409/409、补充包63/63、代码快照14956、分析快照108652均complete。原review_files 7/7已为NAS符号链接，无剩余待确认主权重。剩余855暂缓项仍属于公开可重下载模型、非优先Adam/FP32/RNG状态、中间/工程探针、已可由保留delta重建的完整导出和历史过程文件；没有新的不可重建关键依赖，未扩大迁移范围。

2026-11-15 NAS覆盖审计纠正：前次仅检查已完成状态和checkpoint暂缓清单，未核对全部研究证据的归档覆盖。实际发现GroundJEV outputs、旧U2 results、外置runs及R58独立原始预测未进入三个快照，历史experiment_evidence缺口约92.6GiB（排除plot_dependencies可重建依赖）。本轮先做真实路径/增量扫描，冻结新plan；两路CPU gzip压缩直接写NAS，各包完整解压读回，逐文件SHA256与压缩字节SHA256同时核对，完成包可断点续用。全程copy-only，保留原结果，原始数据/环境/暂缓权重不纳入。实现及双文件压缩/读回/恢复定向回归通过；具体文件数/容量以nas_followup_20261115/plan.json为准。

2026-11-15 23:44 NAS重要研究证据补传进行中：已完成49/58包（含R58独立原始预测、旧U2、外置runs、共享文档及首个9.370GiB大型trace包），不是全量完成。初始清单36309文件，明确修订为36305文件/100702571726字节：排除4个UI临时Git引用164字节（其中2个已自动过期），对被并行审计更新的两份文档取稳定副本；plan_v1.json与plan_amendment_v2.json完整保留。曾出现线程池延迟回报首个失败、NAS SSH banner超时和共享挂载大块I/O缓慢；已修复首错及时记录/取消排队、改用有主机密钥固定校验的两条SFTP连接（banner120秒、元数据4次有界重试）、本地gzip暂存后按32MiB边界续传，所有文件及完整压缩流仍必须NAS读回SHA256一致。512KiB正偏移续传的2MiB实测通过，读写预检通过；本地已压缩文件保留，暂存上限25GiB，源研究数据/模型权重和官方推理代码未修改。另一个groundjev_followup_20261115补充批次已有15/15独立回执、3501068001存储字节与10个历史checkpoint/合约文件；不据此宣称当前research_evidence批次完成。当前控制：analysis/nas_followup_20261115/。


### NAS 20261115 serial transport probe: connection-stage EOF

32 MiB single-handle SFTP probe failed before any payload write: NASClient -> Transport.connect -> start_client -> Packetizer.read_all raised EOFError. Therefore no streaming throughput conclusion and no change/restart of the live transfer. Probe target was never created. Existing session 30244 / wait cell 87 remains live; 49/58 packs have full NAS verification. No source results or model settings changed.


### NAS 20261115 18:13 UTC: terminal connection refusal and targeted repair

Transfer session 30244 / wait cell 87 exited 1 at 18:13 UTC: ConnectionRefusedError connecting 127.0.0.1:24558 during compact_03 upload. Subsequent direct TCP check found the same listener restored. Existing verified receipts remain 49 packs / 29,768 files; 3 local staged archives remain intact. Parent reconnectable() excluded this observed TCP refusal. The followup subclass now adds only ConnectionRefusedError to the existing bounded retry path, without editing the legacy transport. Failure status now distinguishes receipts obtained in this attempt from all locally recorded prior verified packs (the old zero count was per-attempt, not a loss of the 49 receipts). Official weights, inference, results, seeds and frozen payload membership are unchanged.

Prior serial-probe EOF JSON was preserved under its original UTC timestamp before rerunning. Regression: inject exactly one observed connection-refusal exception, then perform real NAS write/read/delete through the bounded reconnect path. A 32 MiB streaming diagnostic is also running; no throughput conclusion yet. Do not interpret test launch as success or start a duplicate main transfer.


### NAS 20261115 refusal fix regression PASS and resume

Targeted refusal recovery passed: one injected refusal, 2 constructor attempts, 45-byte real NAS write/read/delete. Preserved prior diagnostic EOF artifact. Serial 32 MiB write/readback SHA256 passed; write 368.587 s (0.086818 MiB/s), readback 7.513 s (~4.259 MiB/s). Thus no evidence to change the parallel transfer algorithm; resumed existing frozen plan after the minimal retry fix. New main session 83968 / blocking wait cell 126; old session 30244 exited 1. Same 49 verified archives reused; 9 unfinished packs remain. No official inference, weights, seed, source results, or frozen payload membership changed.


### NAS 20261115 compact_03 readback corruption and contiguous-resume regression

Native NAS verification rejected compact_03 with zlib invalid stored block lengths; no acceptance criteria were changed. Local compressed SHA256 and all 557 local members passed the same verifier. CPU seed=2025 reproduction left a hole in range 1 while file length reached 5 MiB: old resume at 5 MiB produced wrong hash; new resume at contiguous acknowledged 1 MiB produced the expected hash. Both before FAIL and after PASS JSON are retained. Fix affects only transfer metadata, not official weights/inference/results. New upload checkpoints advance only after in-order range futures succeed; legacy unverified partials with no valid checkpoint cannot be trusted by length.

NAS corruption root pattern still awaits range comparison; do not claim all-zero holes until observed. Existing native session 83968 is shutting down after its recorded failure while other in-flight packs finish. Wait for its terminal handle before starting repair_uploaded_archive.py. Repair compares every compressed range to the fully validated local stage, changes only mismatched NAS ranges, then calls the exact native archive/member verifier and receipt path. Goal scope remains 58 packs / 36,305 files.


### NAS 20261115 actual all-zero resumed gap located

Old main session83968 is terminal exit1. compact_02 passed full native verification (1066 members), raising total to50 verified packs/30834 files. compact_04 was fully uploaded but has no receipt and remains untrusted. Started sequential repair command for compact_03/04, session57066 / wait cell139. Actual compact_03 compressed range at offset67108864 length33554432 was all zero; range134217728 length33554432 also differed. Both were rewritten from the fully validated local stage and immediately read back byte-equal. This confirms a real gap in the reused prefix, consistent with the CPU reproduction of unsafe file-length-based resume. The implementation error is in prior transfer recovery, not a change in research results. Native full archive/member verification remains required; do not count repaired chunks as completed archives.


### NAS 20261115 both corrupted copies recovered; resume final six packs

Both compact_03 and compact_04 now pass the exact native full archive SHA256 and member checks (557 and 710 source members). Each had three mismatched 32 MiB ranges; total192 MiB rewritten, including an all-zero64–96 MiB range in each NAS copy. Original source files were preserved. Total52 verified packs /32101 files /58601365524 source bytes. Repair session57066 /cell139 exited0. Authentic old NAS helper was frozen and published separately with SHA256 16219464d507238b7074c1b809572847e20f382c4605a728ab104ae4db203159 before replacing the main control code. CPU before_frozen reproduces the original expected FAIL with identical source/actual hashes and5 MiB unsafe resume; corrected code resumes at1 MiB and passes. Failure records retained. Resume remaining6 packs with contiguous-acknowledgement checkpoints; global58-pack audit and final log copy still pending.


### NAS_RESEARCH_EVIDENCE_20261115_COMPLETE

补齐 36,305 个文件、100,702,571,726 源字节，58 个归档、35,431,013,859 NAS 字节。全部 NAS 归档及每个成员的 SHA256 回读通过，completion_audit.json=PASS；原始研究结果与权重保留。此前备份覆盖不足的判断已更正。
完成凭证：/data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101/analysis/nas_followup_20261115/completion_audit.json；NAS：/data2/user/nas/A800/research_evidence_20261115。


## A100 恢复，2026-11-20

按用户要求恢复 YesTrack V2 独立工作区；完整读取原对话 31 页。429 个源码文件从 NAS 冻结包按原清单校验后恢复，官方 YesTrack/TrackEval 和 OneJev 源码未改。历史日志使用 NAS 最新收尾版本；仅 config.json 的位置和执行环境字段更新为 A100。数据、大权重、大型输出和概率缓存仍在 NAS，R58 的36份原始概率已在NAS解包并校验。

验证：官方 TrackEval 汇总862条详细结果得到 HOTA=40.42746189241033；六模型 R58 原始缓存与 LOSO 主属性宏 ECE 复算一致；8008张图像/9758条表达式目录清点和逐序列首帧解码通过，1756个存储链接可访问。原备份明确暂缓的5组R58公开大权重和专用GPU环境尚未恢复，已有CPU缓存可用。研究继续以原R58结论为准：无模型通过全部标准，属性概率直接相乘的可靠性未获支持。详细接续见 CURRENT_STATE.md。


单帧恢复检查的首次默认NAS mmap加载在FUSE页I/O等待超过4分钟，已停止仅此恢复进程；故障保存在 recovery/gpu_mmap_incident.json 与 gpu_smoke_mmap_stall.log。恢复检查改用pinned SFTP连续读取到匿名memfd内存，再调用完全相同的官方建模、crop与forward函数；不把checkpoint写入A100磁盘。该变化只处理恢复检查的I/O，不是新的研究变体。


A100 单帧验证完成：GPU0、官方 V2 LoRA、两个候选，概率为0.96875与0.00860595703125，与原A800记录最大差0。模型与forward耗时10.43秒；包括NAS连续读取共411.78秒。匿名memfd内存传输避开初次FUSE mmap停滞，未在A100磁盘落地权重；临时目录已清理，验证进程正常退出。结果见 recovery/gpu_smoke.json。


## 2026-11-20：GitHub 公开代码归档

按用户要求准备公开仓库 LYQ1107/YesTrackV2。发布分析源码、冻结方案、小型注释、报告、详细研究历程与 A100 恢复脚本；新增 README 阅读入口和上游版本说明。官方 YesTrack/OneJev 以固定 commit 的 submodule 保留，源码未改动。原始聊天、无关项目总日志、环境、NAS 链接、数据集、权重和大型缓存不提交。已检查暂存文件大小与常见凭据模式；本次只整理 Git 归档，没有启动或重跑研究实验。

## 2026-11-20：提交大小上限

用户要求后续所有提交小于 100 MB，已写入根 AGENTS.md，按十进制 100,000,000 字节检查每次提交的文件快照。核对公开 main 的初始提交 111d061：168 个普通文件共 15,024,453 字节，最大文件 5,760,725 字节；完整主仓库历史仅一个提交，均低于上限。子模块独立统计，NAS 数据及权重不计入代码仓库。本次只更新项目约束与记录。
