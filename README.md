shadowsocksrh 是一种网络代理工具，可以使用`http`发送流量和日志信息，实现远程控制用户
请勿将本工具用于违反法律的行为，具体法律条文请参考[中华人民共和国网络安全法](http://www.npc.gov.cn/npc/xinwen/2016-11/07/content_2001605.htm)

## 使用方法：
首先在`userapiconfig`中设置获取用户信息的地址，ID和KEY
程序将首先从`https://<ADDRESS>/Api/Index/fetchUser?id=<ID>&key=<KEY>`获取用户信息
信息格式为：
```json
[{
	"uid":"123",
	"port":"1234",
	"passwd":"12345",
	"protocol":"origin",
	"obfs":"plain",
	"group":"1"
	},
	....
]
```
程序每隔一段时间会向`https://<ADDRESS>/Api/update/fetchUser?id=<ID>&key=<KEY>`返回用户流量信息：
格式为：
```json
[{
	"d": 6467327,
	 "u": 129680,
	 "uid": "23",
	 "port": 2000
	 },
	...
]
```
## 新增功能(测试中）
- 可以在配置文件中设置最多用户数，若获取的用户数多于这个数量，之后的用户将会被关闭端口
- 若将HTTPLOG设置为True，程序将在记录日志的同时，将日志数据发送到`https://<ADDRESS>/Api/log/fetchUser?id=<ID>&key=<KEY>`
  格式为：
```json
	{ "loggerName":"%(name)s",
	"asciTime":"%(asctime)s",
	"fileName":"%(filename)s",
	"logRecordCreationTime":"%(created)f",
	"functionName":"%(funcName)s",
	"levelNo":"%(levelno)s",
	"lineNo":"%(lineno)d",
	"time":"%(msecs)d",
	"levelName":"%(levelname)s",
	"message":"%(message)s"
    }
```

## 启动方式
```shell
python server.py
```



