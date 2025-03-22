import json
import requests

cookies = {
    'JSESSIONID': 'RZ55o2uUsPqN8y6Qzu9wbZhTeiq7XfauthRZ55GZ00',
    'receive-cookie-deprecation': '1',
    'cna': 'jj8KIGM40EgCAX1NW/06Xie1',
    'session.cookieNameId': 'ALIPAYJSESSIONID',
    '_CHIPS-session.cookieNameId': 'ALIPAYJSESSIONID',
    'mobileSendTime': '-1',
    'credibleMobileSendTime': '-1',
    'ctuMobileSendTime': '-1',
    'riskMobileBankSendTime': '-1',
    'riskMobileAccoutSendTime': '-1',
    'riskMobileCreditSendTime': '-1',
    'riskCredibleMobileSendTime': '-1',
    'riskOriginalAccountMobileSendTime': '-1',
    'EXC_ANT_KEY': '"excashier_20001_FP_SENIOR_HJPGP11781032770582,excashier_20001_FP_SENIOR_lh2025022714461844467_2145726,excashier_20001_FP_SENIOR_HJPGP11880646570582,excashier_20001_FP_SENIOR_HJPGP11917853890582"',
    '_CHIPS-csrfToken': '4oSxFEbQ3Wrst35g0-pTcNgn',
    'csrfToken': '4oSxFEbQ3Wrst35g0-pTcNgn',
    '__TRACERT_COOKIE_bucUserId': '2088212888256550',
    'ALI_PAMIR_SID': 'U55k3YfKTtGZmtVpuxTx2kehDU1#fAnFU3cqRBeIW9RUBhM8RzU1',
    'CLUB_ALIPAY_COM': '2088212888256550',
    'ali_apache_tracktmp': '"uid=2088212888256550"',
    'iw.userid': '"K1iSL1vhasuVZ3Ls4+CB+A=="',
    'LoginForm': 'alipay_login_auth',
    'auth_goto_http_type': 'https',
    'ctoken': '1eCDoE_k7ZWeQzvx',
    '_CHIPS-ctoken': '1eCDoE_k7ZWeQzvx',
    'alipay': '"K1iSL1vhasuVZ3Ls4+CB+Hx/46k+X85cpHT+Po/idA=="',
    'auth_jwt': 'e30.eyJleHAiOjE3NDI1ODYzNjk1OTEsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiVGxvaGhDYVU1eEZJTnBNL3haNzZBRVJGZ25mNXdDSmI5ZGJhZWNPIiwidWlkIjoiMjA4ODIxMjg4ODI1NjU1MCJ9.ZG4y6xiwsbEFrh7cnn9ebr52gq3fBEqcErEhgQ2mKF4',
    '_CHIPS-ALIPAYJSESSIONID': 'RZ55o2uUsPqN8y6Qzu9wbZhTeiq7XfauthRZ55GZ00',
    'zone': 'GZ00F',
    'jsh_t_c_e': 'jsh_t_0.1898852262891213',
    'JSESSIONID': '7BBC12E929A16A9DFC382BA49BEA2472',
    'spanner': '9io+tVmsOh6wGoMEPlFI+7n4OFYQaYKs',
    'ALIPAYJSESSIONID': 'RZ55o2uUsPqN8y6Qzu9wbZhTeiq7XfauthGZ00RZ55',
    'rtk': 'zEhxTgN6ckU+xbVjHE2FUQ3gf3SJAV3yF2iiVjAWb0Pkt9wObmY',
}

headers = {
    'accept': 'application/json',
    'accept-language': 'zh-CN,zh;q=0.9',
    'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
    'origin': 'https://c.alipay.com',
    'priority': 'u=1, i',
    'referer': 'https://c.alipay.com/',
    'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    # 'cookie': 'JSESSIONID=RZ55o2uUsPqN8y6Qzu9wbZhTeiq7XfauthRZ55GZ00; receive-cookie-deprecation=1; cna=jj8KIGM40EgCAX1NW/06Xie1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; EXC_ANT_KEY="excashier_20001_FP_SENIOR_HJPGP11781032770582,excashier_20001_FP_SENIOR_lh2025022714461844467_2145726,excashier_20001_FP_SENIOR_HJPGP11880646570582,excashier_20001_FP_SENIOR_HJPGP11917853890582"; _CHIPS-csrfToken=4oSxFEbQ3Wrst35g0-pTcNgn; csrfToken=4oSxFEbQ3Wrst35g0-pTcNgn; __TRACERT_COOKIE_bucUserId=2088212888256550; ALI_PAMIR_SID=U55k3YfKTtGZmtVpuxTx2kehDU1#fAnFU3cqRBeIW9RUBhM8RzU1; CLUB_ALIPAY_COM=2088212888256550; ali_apache_tracktmp="uid=2088212888256550"; iw.userid="K1iSL1vhasuVZ3Ls4+CB+A=="; LoginForm=alipay_login_auth; auth_goto_http_type=https; ctoken=1eCDoE_k7ZWeQzvx; _CHIPS-ctoken=1eCDoE_k7ZWeQzvx; alipay="K1iSL1vhasuVZ3Ls4+CB+Hx/46k+X85cpHT+Po/idA=="; auth_jwt=e30.eyJleHAiOjE3NDI1ODYzNjk1OTEsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiVGxvaGhDYVU1eEZJTnBNL3haNzZBRVJGZ25mNXdDSmI5ZGJhZWNPIiwidWlkIjoiMjA4ODIxMjg4ODI1NjU1MCJ9.ZG4y6xiwsbEFrh7cnn9ebr52gq3fBEqcErEhgQ2mKF4; _CHIPS-ALIPAYJSESSIONID=RZ55o2uUsPqN8y6Qzu9wbZhTeiq7XfauthRZ55GZ00; zone=GZ00F; jsh_t_c_e=jsh_t_0.1898852262891213; JSESSIONID=7BBC12E929A16A9DFC382BA49BEA2472; spanner=9io+tVmsOh6wGoMEPlFI+7n4OFYQaYKs; ALIPAYJSESSIONID=RZ55o2uUsPqN8y6Qzu9wbZhTeiq7XfauthGZ00RZ55; rtk=zEhxTgN6ckU+xbVjHE2FUQ3gf3SJAV3yF2iiVjAWb0Pkt9wObmY',
}

params = {
    'loginPublicId': '2030096236914559',
    'sourceId': 'S',
    'appId': '2030096236914559',
    '_input_charset': 'utf-8',
    '_output_charset': 'utf-8',
    '_ksTS': '1742585825556_5',
    'ctoken': '1eCDoE_k7ZWeQzvx',
}

data = {
    'sourceId': 'sweb',
    'page': '2',
    'pageSize': '10',
    'auditSource': 'QUALITY',
    'statusList': 'all',
}

response = requests.post(
    'https://contentweb.alipay.com/life/publishListV2.json',
    params=params,
    cookies=cookies,
    headers=headers,
    data=data,
)

print(json.loads(response.text))