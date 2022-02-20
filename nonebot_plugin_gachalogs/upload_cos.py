import hmac
import os
import sys
import time
from hashlib import sha1

from nonebot.log import logger

from .__meta__ import getCOSMeta

cosConfig = getCOSMeta()
bucketName = cosConfig["bucketName"]
bucketRegion = cosConfig["bucketRegion"]
secretId = cosConfig["secretId"]
secretKey = cosConfig["secretKey"]


# 计算 COS 文件链接签名表单字段
# https://cos5.cloud.tencent.com/static/cos-sign/
def getSignature(file: str) -> str:
    def toBytes(s: str) -> bytes:
        return s.encode("utf-8")
    # SignKey = HMAC-SHA1(SecretKey, [q-key-time])
    signTime = int(time.time()) - 60
    expireTime = signTime + 3600
    timeStr = f"{signTime};{expireTime}"
    signKey = hmac.new(toBytes(secretKey), toBytes(timeStr), sha1).hexdigest()
    # HttpString = [HttpMethod]\n[HttpURI]\n[HttpParameters]\n[HttpHeaders]\n
    httpString = u"get\n/{}\n\n\n".format(file)
    # StringToSign = [q-sign-algorithm]\n[q-sign-time]\nSHA1-HASH(HttpString)\n
    httpStrSha = sha1(toBytes(httpString)).hexdigest()
    strToSign = u"sha1\n{}\n{}\n".format(timeStr, httpStrSha)
    # Signature = HMAC-SHA1(SignKey,StringToSign)
    sign = hmac.new(toBytes(signKey), toBytes(strToSign), sha1).hexdigest()
    params = [
        "q-sign-algorithm=sha1",
        f"q-ak={secretId}",
        f"q-sign-time={timeStr}",
        f"q-key-time={timeStr}",
        "q-header-list=",
        "q-url-param-list=",
        f"q-signature={sign}",
    ]
    return "&".join(params)


# 初始化 COS 客户端，一个 Bucket 只需一个客户端即可
def initCosClient() -> object:
    if "" in cosConfig.values():
        return None
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        from pip._internal import main as pipmain
        pipmain(['install', "cos-python-sdk-v5"])
        from qcloud_cos import CosConfig, CosS3Client
    except Exception as e:
        logger.error(
            "安装 XML Python SDK 失败："
            + str(sys.exc_info()[0]) + "\n" + str(e)
        )
        return None
    try:
        config = CosConfig(
            Region=bucketRegion, Token=None, Scheme="https",
            SecretId=secretId, SecretKey=secretKey
        )
        client = CosS3Client(config)
        return client
    except Exception as e:
        logger.error(
            "初始化 cos client 失败："
            + str(sys.exc_info()[0]) + "\n" + str(e)
        )
        return None


# 上传文件到 COS
async def uploadFile(client: object, filePath: str) -> str:
    bucketDomain = f"https://{bucketName}.cos.{bucketRegion}.myqcloud.com"
    fileName = filePath.split(os.sep)[-1]
    with open(filePath, "rb") as fp:
        response = client.put_object(
            Bucket=bucketName,
            Body=fp,
            Key=fileName,
            StorageClass="STANDARD",
            EnableMD5=False
        )
    logger.debug("文件上传 Etag：" + response["ETag"])
    urlSigned = f"{bucketDomain}/{fileName}?{getSignature(fileName)}"
    return urlSigned
