# 上游代码与版本

本仓库用于 YesTrack V2 的复现、错误诊断和方法前提检验。两个官方代码库通过 Git submodule 固定版本，保留上游代码及许可。

| 代码 | 本地目录 | 固定 commit | 上游许可 |
|---|---|---|---|
| [YesTrack](https://github.com/ggbondrighthere24/YesTrack) | `yestrack_diagnosis_20261101/analysis/upstream/YesTrack` | `ed42b8315b28c94dc595d83b0d49bf57002bb281` | MIT |
| [OneJev](https://github.com/OmniJev/OneJev) | `external/OneJev` | `2470c7595688c6a402560cf18b4753feb1fe290a` | Apache-2.0 |

TrackEval 位于 YesTrack 的 `TrackEval/` 目录，保留其 MIT 许可。模型、数据集及其使用条件以各自官方发布为准；本仓库不分发模型权重、KITTI 图像或大型预测缓存。

新克隆时使用 `git clone --recurse-submodules`；已有克隆运行 `git submodule update --init --recursive`。submodule 的目标 commit 是本研究使用的版本，请按仓库记录检出。
