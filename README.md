# WebServer

### Запуск проекта
1) Установка зависимостей не требуется  
2) Запуск `python3 httpd.py`

### Результаты ab -n 50000 -c 5 -r http://localhost:8080/
```
Server Software:        My-HTTP-Server
Server Hostname:        localhost
Server Port:            8080

Document Path:          /
Document Length:        171 bytes


Concurrency Level:      5
Time taken for tests:   96.823 seconds
Complete requests:      50000
Failed requests:        9
   (Connect: 3, Receive: 3, Length: 3, Exceptions: 0)
Total transferred:      15499070 bytes
HTML transferred:       8549487 bytes
Requests per second:    516.41 [#/sec] (mean)
Time per request:       9.682 [ms] (mean)
Time per request:       1.936 [ms] (mean, across all concurrent requests)
Transfer rate:          156.32 [Kbytes/sec] received


Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    6 289.5      0   19514
Processing:     0    4 201.3      1   25913
Waiting:        0    2  14.5      1    1252
Total:          0    9 352.6      2   25913


Percentage of the requests served within a certain time (ms)

  perc    ms
  50%      2
  66%      2
  75%      2
  80%      2
  90%      3
  95%      3
  98%      4
  99%      5
 100%  25913 (longest request)
```