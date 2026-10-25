# vLLM 部署规范

## 环境要求
- 操作系统 Ubuntu 22.04，NVIDIA 驱动 ≥ 550，CUDA 12.4。
- 使用官方 vLLM 镜像，镜像版本在交付文档中锁定。

## 部署参数
- `--tensor-parallel-size` 等于单机 GPU 数。
- `--max-num-seqs` 不低于合同约定的并发数。
- `--gpu-memory-utilization` 默认 0.9，显存紧张时不得超过 0.95。

## 监控与运维
- 标准版及以上必须部署 Prometheus + Grafana，监控首 token 延迟、吞吐和显存占用。
- 维保期内提供远程巡检，每季度一次。
