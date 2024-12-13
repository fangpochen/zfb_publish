import hashlib
import json
import os
import secrets
import time
import urllib
import concurrent.futures
import requests
import sqlite3
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions


def create_table():
    conn = sqlite3.connect('User_Data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_data';")
    table_exists = cursor.fetchone()
    if not table_exists:
        cursor.execute('''
        CREATE TABLE user_data (
            appid CHAR(64) PRIMARY KEY,
            cookies TEXT,
            user_name TEXT,
            request_all TEXT
        )
        ''')
        print("表格创建成功")
    else:
        print("表格已存在")
    conn.commit()
    conn.close()


# create_table()
def get_appid(cookies):
    '''

    :param cookies: 传入cookie
    :return:  返回用户的appid
    '''
    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        # 'cookie': 'JSESSIONID=RZ43Fk6xgZEXlmuXKkMG4PLc5kSSMTauthRZ42GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; auth_goto_http_type=https; ctoken=9wKSgr_kG8zycmgQ; _CHIPS-ctoken=9wKSgr_kG8zycmgQ; LoginForm=alipay_login_home; alipay="K1iSL19mwb+fHm8DIo6SzyPb35M2atCZSixKUi1DCw=="; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; auth_jwt=e30.eyJleHAiOjE3MzM2NzM2MTI1MTgsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiT2d4VzJnOEhOeU9pUkxNc3lhRTQ0SFhGZ2V0TUlwdGUxYmNhNjdiIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.GmIxvPXX0zwtUTGwOlP9QCU_SPJDkoEn65Md-LJwS90; _CHIPS-ALIPAYJSESSIONID=RZ43Fk6xgZEXlmuXKkMG4PLc5kSSMTauthRZ42GZ00; ALIPAYJSESSIONID=RZ43Fk6xgZEXlmuXKkMG4PLc5kSSMTauthRZ42GZ00; rtk=aycvC3UK1/YGP+xr5yOZifWQIOxfxnCVjPagrm8p1Zidxn4T1jU; __TRACERT_COOKIE_bucUserId=2088642500352911; zone=GZ00G; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#/WtSNKt2SHa3IqX061Rhdzkx"; JSESSIONID=B7B3893F2D1FA8511BE4B89AEE85D2E2; spanner=sDmQ/tfsbusli0eTx1P4ZmbZwowxMu3ZXt2T4qEYgj0=',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }

    params = {
        'sourceId': 'S',
    }

    response = requests.get('https://contentweb.alipay.com/life/getAppEnv.json', params=params, cookies=cookies,
                            headers=headers)
    json_data = response.json()
    print(json_data)
    result = json_data.get('result')
    appname = result.get('appName')
    appId = result.get('appId')
    print(f'获取appid成功：{appId}')
    return str(appId), appname


# 登录
def login():
    conn = sqlite3.connect('User_Data.db')
    cursor = conn.cursor()
    ''''
    return :返回cookie和保持cookie所用的请求数据data
    '''
    co = ChromiumOptions()
    co.set_argument('--window-size', '800,600')
    page = ChromiumPage(co)
    page.get('https://c.alipay.com/page/content-creation/publish/short-video?appId=2030095407214168')
    page.wait.url_change('https://c.alipay.com/page/content-creation/publish/short-video?appId=2030086492507825')
    page.listen.start('dwcookie?biztype=pcwallet')
    context = page.ele('@@text()=内容发布').click()
    packets = page.listen.wait(5)
    # print(packets)
    cookies_list = page.cookies()
    cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
    appid, user_name = get_appid(cookies_dict)
    all_request = []
    for packet in packets:
        request_data = dict()
        request_data['url'] = packet.url
        request_data['data'] = packet.request.postData
        all_request.append(request_data)
    page.quit()
    cursor.execute('''
    INSERT OR REPLACE INTO user_data (appid, cookies, user_name, request_all) 
    VALUES (?, ?, ?, ?)
    ''', (appid, str(cookies_dict), user_name, str(all_request)))
    conn.commit()
    conn.close()
    return cookies_dict, appid, user_name, all_request


login()


# 保持cookie
def keep_cookies(url, data):
    '''
       :param data: 传入
       '''
    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    data = f'{data}'
    response = requests.post(url, headers=headers, data=data)
    jsondata = response.json()
    code = jsondata['code']
    code_v2 = jsondata['code_v2']
    if code == 200 and code_v2 == 200:
        return True
    else:
        return False


# 获取appid

# get_appid(cookies)
# 获取视频列表
def get_public_list(cookies, appid, type):
    '''
    :param cookies:传入cookies
    :param appid:用户的id
    :param type:使用类型，传入'delete'是获取需要删除的视频列表，传入recommend为获取当日推荐视频列表
    :return:
    返回需要删除的视频id，或者推荐视频id
    '''
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        # 'cookie': 'JSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authRZ42GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; __TRACERT_COOKIE_bucUserId=2088642500352911; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#bnz+ctsBQbm5M9QJsMj9Vjkx"; ctoken=Z-dPkcYColZussmH; _CHIPS-ctoken=Z-dPkcYColZussmH; LoginForm=alipay_login_auth; auth_jwt=e30.eyJleHAiOjE3MzM2MjU5NjYzNjEsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiSnQ5YmMzZWE4a1dIRzJib3pKSUp5ZDFYRjIwa2dGZ0lBcXRPQWtBIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.npZb6KjqQ8TQrainac26ahDx1toiR3gEAk-acJZQHhc; rtk=ln/sySw8Nl2Nvu51xn/mC7sXF/575yib0vl21ZRcrmC45ydJr0w; _CHIPS-ALIPAYJSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authGZ00RZ43; ALIPAYJSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authRZ43GZ00; zone=GZ00G; JSESSIONID=755D2546CB0D857145466FC7902813C5; spanner=TFXHJ4uXsSqN2bxWf2KfwQ9UcXGcquKG4EJoL7C0n0A=',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    params = {
        'loginPublicId': f'{appid}',
        'sourceId': 'S',
        'appId': f'{appid}',
        '_input_charset': 'utf-8',
        '_output_charset': 'utf-8',

        '_ksTS': '1733630499679_14',
        'ctoken': 'Z-dPkcYColZussmH',
    }
    stop = False
    delete_id_list = []
    Recommended_list = []
    if type == 'delete':
        while not stop:
            page = 1
            data = {
                'sourceId': 'sweb',
                'page': f'{page}',
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
            result = response.json().get('result')
            publishContents = result.get('publishContents')
            for item in publishContents:
                rec_data = dict()
                state = item.get('state')
                if state == '已发布':
                    canContentRecommended = item.get('canContentRecommended')
                    if canContentRecommended == True:
                        pass
                        # rec_data['id']=item.get('contentId')
                        # rec_data['title']=item.get('title')
                        # Recommended_list.append(rec_data)
                    else:
                        contentId = item.get('contentId')
                        delete_id_list.append(contentId)

            if not publishContents or len(publishContents) < 10:
                stop = True

            return delete_id_list
    elif type == 'recommend':
        current_date = datetime.now()
        formatted_date = current_date.strftime('%Y%m%d')
        while not stop:
            page = 1
            data = {
                'sourceId': 'sweb',
                'page': f'{page}',
                'pageSize': '10',
                'startDate': f'{formatted_date}',
                'endDate': f'{formatted_date}',
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
            result = response.json().get('result')
            publishContents = result.get('publishContents')
            for item in publishContents:
                rec_data = dict()
                state = item.get('state')
                if state == '已发布':
                    canContentRecommended = item.get('canContentRecommended')
                    if canContentRecommended == True:
                        rec_data['id'] = item.get('contentId')
                        rec_data['title'] = item.get('title')
                        Recommended_list.append(rec_data)
                    else:
                        pass
                        # contentId = item.get('contentId')
                        # delete_id_list.append(contentId)

            if not publishContents or len(publishContents) < 10:
                stop = True
        return Recommended_list
    else:
        return None


##删除不推荐视频
def delete_note(cookies, id_listm, appid):
    '''
      :param cookies:传入cookies
      :param appid:用户的id
      :param id_listm:需要删除的视频id列表
      '''
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        # 'cookie': 'JSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authRZ42GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; __TRACERT_COOKIE_bucUserId=2088642500352911; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#bnz+ctsBQbm5M9QJsMj9Vjkx"; ctoken=Z-dPkcYColZussmH; _CHIPS-ctoken=Z-dPkcYColZussmH; LoginForm=alipay_login_auth; auth_jwt=e30.eyJleHAiOjE3MzM2MjU5NjYzNjEsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiSnQ5YmMzZWE4a1dIRzJib3pKSUp5ZDFYRjIwa2dGZ0lBcXRPQWtBIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.npZb6KjqQ8TQrainac26ahDx1toiR3gEAk-acJZQHhc; rtk=ln/sySw8Nl2Nvu51xn/mC7sXF/575yib0vl21ZRcrmC45ydJr0w; _CHIPS-ALIPAYJSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authGZ00RZ43; ALIPAYJSESSIONID=RZ43AjvOOuW0ykYPEbAi3jKXbXFWh0authRZ43GZ00; zone=GZ00G; JSESSIONID=D7B73594156831D45F54EB4DE44A2D8B; spanner=Jvs5gUaFRjnpFelks+N7jOytew30C/SfXt2T4qEYgj0=',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    for note_id in id_listm:
        data = {
            'contentId': f'{note_id}',
            'bizOwner': 'LIFE',
            'sourceId': 'sweb',
        }
        params = {
            'sourceId': 'S',
            'appId': f'{appid}',
            '_input_charset': 'utf-8',
            '_output_charset': 'utf-8',
            '_ksTS': '1733658548854_5',
            'ctoken': 'Z-dPkcYColZussmH',
        }
        response = requests.post(
            'https://contentweb.alipay.com/life/recall.json',
            params=params,
            cookies=cookies,
            headers=headers,
            data=data,
        )
        print(response.json())
        print(f'视频{appid}已删除')


# 获取参加可参加活动:
def get_recomment_tasks(cookies, appid):
    '''
          :param cookies:传入cookies
          :param appid:用户的id
          :return:
          返回可参加任务id列表
          '''
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        # 'cookie': 'JSESSIONID=176CBD10DE01B1F9D5428EB0F9BB9007; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; spanner=XkPiOoqH57LBX8DpqbudpLumcFIkbrTs4EJoL7C0n0A=; auth_goto_http_type=https; umt=Ld88cfefd4afb2413eba1fdca973aa9af; JSESSIONID=9388745E1BCF08B4FC77DC56638B1F89; ctoken=ml0GAin-nlx2oNeg; _CHIPS-ctoken=ml0GAin-nlx2oNeg; LoginForm=alipay_login_home; alipay="K1iSL19mwb+fHm8DIo6SzyPb35M2atCZSixKUi1DCw=="; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; auth_jwt=e30.eyJleHAiOjE3MzM2NzI2MjIxNjQsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiVzcxeVZ5TmlWeFJTa2c4N3g0R2xSZ1ZGZ1VnY2lEOVo0ZTdlNGNRIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.ZDq42nh-UgWWuz7lraXFXHDsKDxfZqh5W3k2d9JHvXA; rtk=ln0gqSwJpagNvu51xn/mC7sXF/575yib0vl21ZRcrmC45ydJr0w; __TRACERT_COOKIE_bucUserId=2088642500352911; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#pLfqLzIRSAqY/mnvlGyNJzkx"; _CHIPS-ALIPAYJSESSIONID=RZ433lutTl2iKJOuLtNZv4Ra7SJLXVauthGZ00RZ43; zone=GZ00G; ALIPAYJSESSIONID=RZ433lutTl2iKJOuLtNZv4Ra7SJLXVauthRZ43GZ00',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    params = {
        'sourceId': 'S',
        'appId': f'{appid}',
        '_input_charset': 'utf-8',
        '_output_charset': 'utf-8',
        '_ksTS': '1733672372270_16',
        'ctoken': 'ml0GAin-nlx2oNeg',
    }
    data = {
        'targetId': f'{appid}',
        'bizScene': 'CREATOR_GROWTH_TASK',
        'requestSource': 'S',
    }
    taskId_list = []
    response = requests.post(
        'https://fuwu.alipay.com/platform/getNewPlatformTasks.json',
        params=params,
        cookies=cookies,
        headers=headers,
        data=data,
    )
    json_data = response.json()
    result = json_data.get('result')
    taskDetailVOS = result.get('taskDetailVOS')
    for task in taskDetailVOS:
        taskId = task.get('taskId')
        taskId_list.append(taskId)
    return taskId_list


# 参加活动：
def collecting_tasks(cookies, appid, taskId_list):
    '''
              :param cookies:传入cookies
              :param appid:用户的id
              :param taskId_list:可参加任务的id列表
              '''
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        # 'cookie': 'JSESSIONID=176CBD10DE01B1F9D5428EB0F9BB9007; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; cna=iEUyH7Q98FICAYvisk82DHns; receive-cookie-deprecation=1; session.cookieNameId=ALIPAYJSESSIONID; _CHIPS-session.cookieNameId=ALIPAYJSESSIONID; spanner=XkPiOoqH57LBX8DpqbudpLumcFIkbrTs4EJoL7C0n0A=; auth_goto_http_type=https; umt=Ld88cfefd4afb2413eba1fdca973aa9af; JSESSIONID=9388745E1BCF08B4FC77DC56638B1F89; ctoken=ml0GAin-nlx2oNeg; _CHIPS-ctoken=ml0GAin-nlx2oNeg; LoginForm=alipay_login_home; alipay="K1iSL19mwb+fHm8DIo6SzyPb35M2atCZSixKUi1DCw=="; CLUB_ALIPAY_COM=2088642500352911; iw.userid="K1iSL19mwb+fHm8DIo6Szw=="; ali_apache_tracktmp="uid=2088642500352911"; auth_jwt=e30.eyJleHAiOjE3MzM2NzI2MjIxNjQsInJsIjoiNSwwLDI3LDE5LDI4LDMwLDEzLDEwIiwic2N0IjoiVzcxeVZ5TmlWeFJTa2c4N3g0R2xSZ1ZGZ1VnY2lEOVo0ZTdlNGNRIiwidWlkIjoiMjA4ODY0MjUwMDM1MjkxMSJ9.ZDq42nh-UgWWuz7lraXFXHDsKDxfZqh5W3k2d9JHvXA; rtk=ln0gqSwJpagNvu51xn/mC7sXF/575yib0vl21ZRcrmC45ydJr0w; __TRACERT_COOKIE_bucUserId=2088642500352911; ALI_PAMIR_SID="U91ezshIDh/BOFs7HksnaCnzTkx#pLfqLzIRSAqY/mnvlGyNJzkx"; _CHIPS-ALIPAYJSESSIONID=RZ433lutTl2iKJOuLtNZv4Ra7SJLXVauthGZ00RZ43; zone=GZ00G; ALIPAYJSESSIONID=RZ433lutTl2iKJOuLtNZv4Ra7SJLXVauthRZ43GZ00',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    for taskId in taskId_list:
        print(appid)
        params = {
            'sourceId': 'S',
            'appId': f'{appid}',
            '_input_charset': 'utf-8',
            '_output_charset': 'utf-8',
            '_ksTS': '1733818224706_15',
            'ctoken': 'mtkiWnGmHrI9WE2K',
        }

        data = {
            'targetId': f'{appid}',
            'bizScene': 'CREATOR_GROWTH_TASK',
            'requestSource': 'S',
            'taskIds': f'{taskId}',
        }

        response = requests.post(
            'https://fuwu.alipay.com/platform/receiveNewPlatformTasks.json',
            params=params,
            cookies=cookies,
            headers=headers,
            data=data,
        )
        print(response.json())
        print(f'任务{taskId}领取成功')


def get_mt(cookies):
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        # 'cookie': 'JSESSIONID=RZ550RyGPQrtw5mQvhYIbEpl3OwPXdauthRZ43GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; session.cookieNameId=ALIPAYJSESSIONID; cna=ova4H2k/PjoBASQOA3pmflO9; receive-cookie-deprecation=1; tfstk=fjASH1YyuuqS85MrCy3VcDAkuYfQLHGw2y_pSeFzJ_CRAMKp24Xe840BhH-vzMkuUKsBDnsRU85FOHtXDUWEreUCJn5RKLSF4M1B-hgqbflwrUfhMcoZ_-l8X61gpze8YoFAz4Yt0RlwrU4Aut_oafrCoxd62MKdetBA8iU8pHBpkjIc-wERJ73jlwjYwuCLejFARaU8pHCKlEIcJb2T5wM5qUgqX06jAmckriNL1PvVebLzLWPeGa6W9ejfFTOfPTsOn39DdQK2JQRlnxyctEJ6ApKnQ-fWJLCR7Uc7G1LJ3B_2T2yC23AXkQXb75WWpw6O9taL9E1lctdC6fEfoKLypQx7RWQkaCWCjtgLt95v_Op9Vy0Mk_QpxOAEj7jJJFAMQ1G4e1LXph9C4dNNfEVLdr6gOZsZlqw3KESn1BlzzPIPeZb53qgb2pXRoZswTqwkKTQcPNujluph.; EXC_ANT_KEY=excashier_20001_FP_SENIOR_HJPGP11505070830582; LoginForm=alipay_login_auth; CLUB_ALIPAY_COM=2088442960985162; iw.userid="K1iSL120ipFvFLCnWp3Rzw=="; ali_apache_tracktmp="uid=2088442960985162"; ALI_PAMIR_SID=U16UPhMbPMFmHACo+5UbbeIqTE2#v7dhBGJlS0WhITjHKU3RJTE2; __TRACERT_COOKIE_bucUserId=2088442960985162; auth_goto_http_type=https; ctoken=R6PCbj3w7TAYSw-o; _CHIPS-ctoken=R6PCbj3w7TAYSw-o; alipay="K1iSL120ipFvFLCnWp3Rz9W5rYlr9VP9dcKwk8Zv/g=="; auth_jwt=e30.eyJleHAiOjE3MzM3NTIyMDcyOTIsInJsIjoiNSwwLDI3LDE5LDI5LDEzLDEwIiwic2N0IjoiY1NQbERpWU5DK3pJRW5ja0V5NE1vK2lGTHhXeHlhSmI1OGYwM2V2IiwidWlkIjoiMjA4ODQ0Mjk2MDk4NTE2MiJ9._DCO3Uk3vQWyIwid3mx_QH_QS2jyx2GF_jnJAvElo-s; _CHIPS-ALIPAYJSESSIONID=RZ550RyGPQrtw5mQvhYIbEpl3OwPXdauthRZ43; zone=GZ00F; ALIPAYJSESSIONID=RZ550RyGPQrtw5mQvhYIbEpl3OwPXdauthRZ43GZ00; rtk=bXk6Oqseuv4JU4DLLXnqJ9ojkfUMBQACD3KTlhIozGT2BQgizes; userId=2088442960985162; JSESSIONID=C3C2EBAE3D29394EBDCF0CD321DACF66; spanner=YAtShxmvaflihRYh57A31ceymNvmR9/NXt2T4qEYgj0=',
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }

    params = {
        'type': 'VIDEO',
    }

    response = requests.get('https://contentweb.alipay.com/life/queryMasstoken.json', params=params, cookies=cookies,
                            headers=headers)
    return json.loads(response.text).get("result").get("massToken")


def get_traid():
    l = "useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict"
    Ft = 21
    return ''.join(secrets.choice(l) for _ in range(Ft))


def upload_4m_video(mt, file_path):
    # 获取文件大小（字节数）
    file_size = os.path.getsize(file_path)

    # 4MB = 4 * 1024 * 1024 字节
    max_size = 4 * 1024 * 1024  # 4MB

    if file_size > max_size:
        return upload_large_video(mt, file_path, file_size)
    # 打开文件
    with open(file_path, 'rb') as file:
        # 构建文件数据
        files = {
            'file': (file.name, file, 'video/mp4')  # 'file' 是表单字段名，file.name 是文件名，'video/mp4' 是文件的 MIME 类型
        }

        # 构建请求头
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Origin': 'https://c.alipay.com',
            'Referer': 'https://c.alipay.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'X-Mass-Appkey': 'apwallet',
            'X-Mass-Biztype': 'content_lifetab',
            'X-Mass-Cust-Conf': '{"extern":{"isWaterMark":true}}',
            'X-Mass-Token': mt,  # 请替换成你的实际 token
            'Connection': 'keep-alive'
        }

        # 发送 POST 请求
        url = f'https://mass.alipay.com/file/auth/upload?mt={mt}&bz=content_lifetab&public=false'
        response = requests.post(url, headers=headers, files=files)
        file_id = json.loads(response.text).get('data').get('id')
        return file_id, file.name


def upload_large_video(mt, file_path, file_size):
    # 打开文件
    with open(file_path, 'rb') as file:
        # 构建文件数据
        files = {
            'file': (file.name, file, 'video/mp4')  # 'file' 是表单字段名，file.name 是文件名，'video/mp4' 是文件的 MIME 类型
        }

        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'origin': 'https://c.alipay.com',
            'priority': 'u=1, i',
            'referer': 'https://c.alipay.com/',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'x-mass-appkey': 'apwallet',
            'x-mass-biztype': 'content_lifetab',
            'x-mass-cust-conf': '{"extern":{"isWaterMark":true}}',
            'x-mass-file-length': '9435271',
            'x-mass-file-md5': calculate_file_md5(file),
            'x-mass-file-multipart-slice-size': '4194304',
            'x-mass-filename': urllib.parse.quote(file.name),
            'x-mass-public': 'false',
            'x-mass-token': mt,
            'x-mass-traceid': get_traid(),
        }

        response = requests.post('https://mass.alipay.com/file/multipart/upload/claim', headers=headers)
        file_id = json.loads(response.text).get('data').get('fileId')
    with open(file_path, 'rb') as file:
        # 设置分割后的最大文件大小
        max_size = 4 * 1024 * 1024  # 4MB

        # 计算文件的分块数
        num_parts = (file_size // max_size) + (1 if file_size % max_size else 0)

        # 开始分块上传
        for i in range(num_parts):
            # 读取每个分块的数据
            part_data = file.read(max_size)
            if not part_data:
                break  # 如果没有数据，退出

            # 构建每个分块上传的请求头
            part_filename = f"{file_path}_part_{i + 1}"
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'origin': 'https://c.alipay.com',
                'referer': 'https://c.alipay.com/',
                'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'x-mass-appkey': 'apwallet',
                'x-mass-biztype': 'content_lifetab',
                'x-mass-file-multipart-id': file_id,
                'x-mass-file-multipart-length': str(len(part_data)),
                'x-mass-file-multipart-num': str(i + 1),
                'x-mass-file-multipart-start': str(i * 4194304),
                'x-mass-token': mt,
                'x-mass-traceid': get_traid()
            }

            # 上传分块数据
            files = {
                'file': ('blob', part_data, 'application/octet-stream'),
            }

            response = requests.post('https://mass.alipay.com/file/multipart/upload/part', headers=headers, files=files)
            print(response.json())  # 打印响应信息，检查上传是否成功

    upload_complete(mt, file_id)
    return file_id, file.name


def upload_complete(mt, file_id):
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        # 'content-length': '0',
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'x-mass-appkey': 'apwallet',
        'x-mass-biztype': 'content_lifetab',
        'x-mass-file-multipart-id': file_id,
        'x-mass-token': mt
    }

    response = requests.post('https://mass.alipay.com/file/multipart/upload/complete', headers=headers)
    print(response.json())


def upload_pic():
    file_path = '充电器起火狗狗举动好棒狗子成精了.jpg'
    headers = {
        'accept': 'application/json',
        'accept-language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'origin': 'https://c.alipay.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }

    # 打开文件
    with open(file_path, 'rb') as file:
        # 构建文件数据
        files = {
            'Filedata': (file.name, file, 'application/octet-stream'),
        }

        response = requests.post('https://contentweb.alipay.com/life/uploadPicAjax.json', cookies=cookies,
                                 headers=headers, files=files)
        return json.loads(response.text).get('extProperty')


def get_video_url(file_id, mt):
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }

    response = requests.get(
        f'https://mmtcapi.alipay.com/video/2.0/convert/query?fileId={file_id}&mt={mt}&bizKey=content_lifetab',
        headers=headers,
    )
    return json.loads(response.text).get('data').get('transCode').get('convertResults')[0].get('url')


def publish(loginPublicId, videoId, videoFile, videoFileName, extProperty, mt, scheduleTime, title):
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/json',
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }

    params = {
        'loginPublicId': loginPublicId,
    }

    json_data = {
        'loginPublicId': loginPublicId,
        'sourceId': 'sweb',
        'videoId': videoId,
        'videoDjangoId': videoId,
        'massToken': mt,
        'videoFile': videoFile,
        'videoFileName': videoFileName,
        'title': title,
        'text': '',
        'canSmartCover': True,
        'canReply': True,
        'canSelectReply': False,
        'canDownload': False,
        'contentType': 2,
        'imageList': [
            {
                'djangoId': extProperty.get('djangoId'),
                'imageUrl': extProperty.get('filePath'),
                'width': extProperty.get('width'),
                'height': extProperty.get('height'),
                'type': 'cover_static',
                'index': 0,
            },
            {
                'djangoId': extProperty.get('djangoId'),
                'imageUrl': extProperty.get('filePath'),
                'width': extProperty.get('width'),
                'height': extProperty.get('height'),
                'type': 'cover_vertical_static',
                'index': 1,
            },
            {
                'djangoId': extProperty.get('djangoId'),
                'imageUrl': extProperty.get('filePath'),
                'width': extProperty.get('width'),
                'height': extProperty.get('height'),
                'type': 'message_cover',
                'index': 2,
            },
        ],
        'offerInfoList': [],
        'scheduleTime': scheduleTime,
        'topicInfoVOList': [],
        'extInfo': {
            'coverSource': 'custom_settings',
        },
    }

    response = requests.post(
        'https://contentweb.alipay.com/life/publishShortVideo.json',
        params=params,
        cookies=cookies,
        headers=headers,
        json=json_data,
    )
    print(response.text)


def get_app_id():
    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9',
        # 'cookie': 'JSESSIONID=RZ55O44FqJ7TLy6FuB56IeP8I1jioTauthRZ43GZ00; mobileSendTime=-1; credibleMobileSendTime=-1; ctuMobileSendTime=-1; riskMobileBankSendTime=-1; riskMobileAccoutSendTime=-1; riskMobileCreditSendTime=-1; riskCredibleMobileSendTime=-1; riskOriginalAccountMobileSendTime=-1; session.cookieNameId=ALIPAYJSESSIONID; cna=ova4H2k/PjoBASQOA3pmflO9; receive-cookie-deprecation=1; tfstk=fjASH1YyuuqS85MrCy3VcDAkuYfQLHGw2y_pSeFzJ_CRAMKp24Xe840BhH-vzMkuUKsBDnsRU85FOHtXDUWEreUCJn5RKLSF4M1B-hgqbflwrUfhMcoZ_-l8X61gpze8YoFAz4Yt0RlwrU4Aut_oafrCoxd62MKdetBA8iU8pHBpkjIc-wERJ73jlwjYwuCLejFARaU8pHCKlEIcJb2T5wM5qUgqX06jAmckriNL1PvVebLzLWPeGa6W9ejfFTOfPTsOn39DdQK2JQRlnxyctEJ6ApKnQ-fWJLCR7Uc7G1LJ3B_2T2yC23AXkQXb75WWpw6O9taL9E1lctdC6fEfoKLypQx7RWQkaCWCjtgLt95v_Op9Vy0Mk_QpxOAEj7jJJFAMQ1G4e1LXph9C4dNNfEVLdr6gOZsZlqw3KESn1BlzzPIPeZb53qgb2pXRoZswTqwkKTQcPNujluph.; EXC_ANT_KEY=excashier_20001_FP_SENIOR_HJPGP11505070830582; LoginForm=alipay_login_auth; CLUB_ALIPAY_COM=2088442960985162; iw.userid="K1iSL120ipFvFLCnWp3Rzw=="; ali_apache_tracktmp="uid=2088442960985162"; ALI_PAMIR_SID=U16UPhMbPMFmHACo+5UbbeIqTE2#v7dhBGJlS0WhITjHKU3RJTE2; __TRACERT_COOKIE_bucUserId=2088442960985162; userId=2088442960985162; auth_goto_http_type=https; ctoken=gwha_z9s2Q7fFA04; _CHIPS-ctoken=gwha_z9s2Q7fFA04; alipay="K1iSL120ipFvFLCnWp3Rz9W5rYlr9VP9dcKwk8Zv/g=="; auth_jwt=e30.eyJleHAiOjE3MzM3NjEzNzQyOTksInJsIjoiNSwwLDI3LDE5LDI5LDEzLDEwIiwic2N0IjoiN1VvMlR2b0pXeGlqNmZ5THhSeTc5Z1RGZy9xM2dOYzY5YjExNGRzIiwidWlkIjoiMjA4ODQ0Mjk2MDk4NTE2MiJ9.iBv6JdB5Iaq4HWm_UgK0hroK58cDunVi-Xp6G_YiAr4; _CHIPS-ALIPAYJSESSIONID=RZ55O44FqJ7TLy6FuB56IeP8I1jioTauthRZ43; zone=GZ00F; ALIPAYJSESSIONID=RZ55O44FqJ7TLy6FuB56IeP8I1jioTauthRZ43GZ00; rtk=D5UPEMOnt+FpPIbyy5BMpuCl6tPqnx3obAScmr4CZ1cRnx8YZVO; JSESSIONID=717E1A1BA7F45E250873B276DABB2C55; spanner=zYmpAhTHmR4faZIwLuJsT2xROgo9NkOZ',
        'origin': 'https://c.alipay.com',
        'priority': 'u=1, i',
        'referer': 'https://c.alipay.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }

    params = {
        'sourceId': 'S',
        'appId': '2030095407214168',
        '_input_charset': 'utf-8',
        '_output_charset': 'utf-8',
        '_ksTS': '1733760780838_1',
        'ctoken': 'gwha_z9s2Q7fFA04',
    }
    response = requests.get('https://contentweb.alipay.com/life/getAppEnv.json', params=params, cookies=cookies,
                            headers=headers)
    return json.loads(response.text).get('result').get('appId')


def calculate_file_md5(file):
    # 创建 MD5 对象
    md5_hash = hashlib.md5()

    chunk_size = 8192
    while chunk := file.read(chunk_size):
        md5_hash.update(chunk)

    # 返回文件的 MD5 值（十六进制表示）
    return md5_hash.hexdigest()


from ratelimit import limits, sleep_and_retry
import time

# 限制每分钟最多处理2个视频
ONE_MINUTE = 60
MAX_REQUESTS_PER_MINUTE = 2


@sleep_and_retry
@limits(calls=MAX_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
def process_single_video(args):
    cookies, file_path, mt, scheduleTime, title = args
    retries = 3  # 最大重试次数

    for attempt in range(retries):
        try:
            file_id, videoFileName = upload_4m_video(mt, file_path)
            extProperty = upload_pic()
            appid = get_app_id()
            time.sleep(10)
            videoFile = get_video_url(file_id, mt)
            publish(appid, file_id, videoFile, videoFileName, extProperty, mt, scheduleTime, title)
            # 发布成功后删除视频文件
            os.remove(file_path)
            print(f"Successfully processed and deleted: {file_path}")
            return True
        except Exception as e:
            if attempt < retries - 1:  # 如果还有重试机会
                print(f"Attempt {attempt + 1} failed for {file_path}: {str(e)}")
                time.sleep(5 * (attempt + 1))
                continue
            else:
                print(f"All attempts failed for {file_path}: {str(e)}")
                return False


def upload_publish_video(cookies, dir_path, title, scheduleTime, max_workers=3):
    """多线程处理视频上传"""
    mt = get_mt(cookies)
    video_files = []

    # 收集所有视频文件路径
    for root, _, files in os.walk(dir_path):
        for file_name in files:
            if file_name.endswith('.mp4'):
                full_path = os.path.join(root, file_name)
                video_files.append(full_path)

    print(f"Found {len(video_files)} video files to process")

    # 准备线程参数
    thread_args = [(cookies, file_path, mt, scheduleTime, title) for file_path in video_files]

    # 使用线程池执行上传任务
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single_video, thread_args))

    # 统计处理结果
    success_count = sum(1 for r in results if r)
    print(f"Processing completed. {success_count} of {len(video_files)} files processed successfully")


if __name__ == '__main__':
    cookies = {
        'JSESSIONID': 'RZ55fkNuVDdcAXJGloIA2TSAsoK4SXauthRZ43GZ00',
        'mobileSendTime': '-1',
        'credibleMobileSendTime': '-1',
        'ctuMobileSendTime': '-1',
        'riskMobileBankSendTime': '-1',
        'riskMobileAccoutSendTime': '-1',
        'riskMobileCreditSendTime': '-1',
        'riskCredibleMobileSendTime': '-1',
        'riskOriginalAccountMobileSendTime': '-1',
        'session.cookieNameId': 'ALIPAYJSESSIONID',
        'cna': 'ova4H2k/PjoBASQOA3pmflO9',
        'receive-cookie-deprecation': '1',
        'tfstk': 'fjASH1YyuuqS85MrCy3VcDAkuYfQLHGw2y_pSeFzJ_CRAMKp24Xe840BhH-vzMkuUKsBDnsRU85FOHtXDUWEreUCJn5RKLSF4M1B-hgqbflwrUfhMcoZ_-l8X61gpze8YoFAz4Yt0RlwrU4Aut_oafrCoxd62MKdetBA8iU8pHBpkjIc-wERJ73jlwjYwuCLejFARaU8pHCKlEIcJb2T5wM5qUgqX06jAmckriNL1PvVebLzLWPeGa6W9ejfFTOfPTsOn39DdQK2JQRlnxyctEJ6ApKnQ-fWJLCR7Uc7G1LJ3B_2T2yC23AXkQXb75WWpw6O9taL9E1lctdC6fEfoKLypQx7RWQkaCWCjtgLt95v_Op9Vy0Mk_QpxOAEj7jJJFAMQ1G4e1LXph9C4dNNfEVLdr6gOZsZlqw3KESn1BlzzPIPeZb53qgb2pXRoZswTqwkKTQcPNujluph.',
        'EXC_ANT_KEY': 'excashier_20001_FP_SENIOR_HJPGP11505070830582',
        'CLUB_ALIPAY_COM': '2088442960985162',
        'ali_apache_tracktmp': '"uid=2088442960985162"',
        'ALI_PAMIR_SID': 'U16UPhMbPMFmHACo+5UbbeIqTE2#v7dhBGJlS0WhITjHKU3RJTE2',
        '__TRACERT_COOKIE_bucUserId': '2088442960985162',
        'userId': '2088442960985162',
        'auth_goto_http_type': 'https',
        'umt': 'HB52d13f5434598308f19d58a857c8a91c',
        'ctoken': 'kuR774LM4a0zEiuw',
        '_CHIPS-ctoken': 'kuR774LM4a0zEiuw',
        'LoginForm': 'alipay_login_home',
        'iw.userid': '"K1iSL120ipFvFLCnWp3Rzw=="',
        'auth_jwt': 'e30.eyJleHAiOjE3MzM4NDA4Mjk3ODIsInJsIjoiNSwwLDI3LDE5LDI5LDEzLDEwIiwic2N0IjoieHNaRUZqNTI1Rm5maFZ1Z0ZIa2VMYXdGZzI0c2cvL3YxZDRiNmFzIiwidWlkIjoiMjA4ODQ0Mjk2MDk4NTE2MiJ9.MldCJpGyk2Ap9mbui5BpO80UoVAN9bkQ4_B-aKk18oc',
        '_CHIPS-ALIPAYJSESSIONID': 'RZ55fkNuVDdcAXJGloIA2TSAsoK4SXauthGZ00RZ55',
        'ALIPAYJSESSIONID': 'RZ55fkNuVDdcAXJGloIA2TSAsoK4SXauthRZ55GZ00',
        'rtk': '0L2QuAPvdP8oO8aXXLxAotAAxG61QBqpaMkYNhgJGzYFQBIcGlP',
        'zone': 'GZ00F',
        'JSESSIONID': '46DD26910BFA152C3007113914D470E6',
        'spanner': 'R7aw/GnSb5q1jDUC97hQRX4uGfBBQTb2Xt2T4qEYgj0=',
    }
    dir_path = "your/video/directory"
    upload_publish_video(cookies, dir_path, max_workers=3)  # 设置3个线程并行处理
