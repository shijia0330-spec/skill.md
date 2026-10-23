# 性能瓶颈检查清单

## CPU 瓶颈

- [ ] CPU 使用率 > 80%
- [ ] 响应时间随并发线性增长
- [ ] 系统 CPU（sys）占比高 > 20%
- [ ] 频繁 GC（Java）
- [ ] 算法复杂度高（嵌套循环、正则回溯）

## 内存瓶颈

- [ ] 内存持续增长不释放
- [ ] 频繁 Full GC
- [ ] 大对象缓存未设置过期
- [ ] 连接池/线程池未释放
- [ ] 内存泄漏（重启后恢复）

## 数据库瓶颈

- [ ] 慢查询日志有记录
- [ ] 锁等待时间增长
- [ ] 连接池耗尽
- [ ] 索引缺失或失效
- [ ] 全表扫描

## 网络瓶颈

- [ ] 带宽利用率 > 80%
- [ ] DNS 解析慢
- [ ] TCP 重传率高
- [ ] 连接数打满

## 中间件瓶颈

- [ ] Redis 连接池耗尽
- [ ] Redis 慢查询
- [ ] MQ 消息堆积
- [ ] 消息消费延迟

## 排查命令

```bash
# CPU/内存
top -c -p $(pgrep -d, -f java)

# 磁盘 IO
iostat -x 1

# 网络
netstat -an | grep ESTABLISHED | wc -l

# 数据库慢查询
tail -f /var/log/mysql/slow.log

# Redis 慢查询
redis-cli slowlog get 10
```
