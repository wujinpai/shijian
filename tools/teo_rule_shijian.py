import teo
z='zone-3uu4zgt2ynxe'
H="${http.request.host} in ['shijian.jisu.cn']"
rule={"RuleName":"诗笺-shijian.jisu.cn","Status":"enable","Branches":[{"Condition":H,
 "Actions":[{"Name":"HostHeader","HostHeaderParameters":{"Action":"custom","ServerName":"sapi.jisu.cn"}},
  {"Name":"Cache","CacheParameters":{"CustomTime":{"Switch":"on","CacheTime":5184000,"IgnoreCacheControl":"on"}}},
  {"Name":"CacheKey","CacheKeyParameters":{"FullURLCache":"on","IgnoreCase":"off","QueryString":{"Switch":"off"}}},
  {"Name":"StatusCodeCache","StatusCodeCacheParameters":{"StatusCodeCacheParams":[{"StatusCode":c,"CacheTime":0} for c in [400,403,404,500,502,503,504]]}}],
 "SubRules":[
  {"Branches":[{"Condition":"${http.request.uri.path} in ['/api/v1/*']","Actions":[{"Name":"MaxAge","MaxAgeParameters":{"FollowOrigin":"off","CacheTime":86400}}]}]},
  {"Branches":[{"Condition":"${http.request.uri.path} in ['/api/v1/random', '/api/v1', '/api/v1/', '/api', '/api/']","Actions":[{"Name":"Cache","CacheParameters":{"NoCache":{"Switch":"on"}}}]}]}
 ]}]}
rule['RuleId']='rule-3x1gcjdfcmnj'
print(teo.call('ModifyL7AccRule',{'ZoneId':z,'Rule':rule}))
