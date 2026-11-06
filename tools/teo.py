import json,sys,os
from tencentcloud.common import credential
from tencentcloud.common.common_client import CommonClient
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
p=os.path.join(os.path.dirname(__file__),'../../.secrets/tencent-api')
sid,sk=open(p).read().split()[:2]
def call(action,params={},ver="2022-09-01",svc="teo",region=""):
    hp=HttpProfile(endpoint=f"{svc}.tencentcloudapi.com")
    c=CommonClient(svc,ver,credential.Credential(sid,sk),region,profile=ClientProfile(httpProfile=hp))
    return c.call_json(action,params)
if __name__=="__main__":
    a=sys.argv[1]; pr=json.loads(sys.argv[2]) if len(sys.argv)>2 else {}
    print(json.dumps(call(a,pr),ensure_ascii=False,indent=1))
