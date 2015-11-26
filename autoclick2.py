#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import getopt
import random
import time
import csv
import codecs
import subprocess
import ConfigParser
import MySQLdb
import datetime 

from selenium import webdriver
from selenium.webdriver.common.proxy import *
from selenium.webdriver.support.ui import Select
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException

browser = None
db = None
cursor = None

logged_in = False

# randomize click
def autoclick_sparse_click(dom_element):
    global browser

    random.seed(None)

    h = dom_element.size['height']
    w = dom_element.size['width']
  
    xoff = random.randint(w/2 - w/3, w/2 + w/3)
    yoff = random.randint(h/2 - h/3, h/2 + h/3)       

    try:
        action = ActionChains(browser)
        action.move_to_element_with_offset(dom_element, xoff, yoff)
        action.click()
        action.perform()
    except NoSuchElementException as err:
        return False

    return True

def autoclick_login_ya(ya_context):
    global browser, logged_in
  
    url_auth = "https://passport.yandex.ru/auth"
    url_direct = "https://direct.yandex.ru/registered/main.pl?cmd=showCamps"
    
    proxy = Proxy({
        'proxyType': ProxyType.MANUAL,
        'httpProxy': ya_context['proxy'],
        'ftpProxy': ya_context['proxy'],
        'sslProxy': ya_context['proxy'],
        'noProxy' : ''
    })

    stream_type = "application/octet-stream;application/csv;text/csv;application/vnd.ms-excel;"
    
    profile = webdriver.FirefoxProfile()
    profile.set_preference('browser.download.folderList', 2)
    profile.set_preference('browser.download.manager.showWhenStarting', False)
    profile.set_preference('browser.download.dir', ya_context['download'])
    profile.set_preference('browser.helperApps.neverAsk.saveToDisk', stream_type)
    profile.set_preference("browser.cache.disk.enable", False)
    profile.set_preference("browser.cache.memory.enable", False);
    profile.set_preference("browser.cache.offline.enable", False);
    profile.set_preference("network.http.use-cache", False);
     
    browser = webdriver.Firefox(proxy=proxy, firefox_profile=profile)
    browser.set_window_size(ya_context['resolution_w'], ya_context['resolution_h'])
    browser.get(url_auth)
    
    try:
        login  = browser.find_element_by_xpath("//input[@id='login']")
        passwd = browser.find_element_by_xpath("//input[@id='passwd']")
        submit = browser.find_element_by_xpath("//button[@type='submit']")
    except NoSuchElementException as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return False
 
    login.clear()
    login.send_keys(ya_context['login'])
    passwd.clear()
    passwd.send_keys(ya_context['password'])
    
    autoclick_sparse_click(submit)
   
    try:
        captcha = browser.find_element_by_xpath('//img[contains(@class, captcha) and contains(@src, captcha)]')
        captcha_ans = browser.find_element_by_xpath('//input[contains(@id, "captcha_answer")]')
    except NoSuchElementException as err:
        pass
     
    time.sleep(5)     

    browser.get(url_direct)   

    try:
        blocked = browser.find_element_by_xpath('//p[@class="p-common-error__message"]').text;
        query_fmt = 'UPDATE account SET status=\"%s\" WHERE id=%s'
        query = query_fmt % ("blocked", ya_context['id']) 
        try:
            cursor.execute(query) 
            db.commit()
        except MySQLdb.Error as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return False
    except NoSuchElementException:
        query_fmt = 'UPDATE account SET status=\"%s\" WHERE id=%s'
        query = query_fmt % ("active", ya_context['id'])
        try: 
            cursor.execute(query) 
            db.commit()
        except MySQLdb.Error as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return False

    logged_in = True

    return True

def autoclick_read_conf(path):
    try:
        config = ConfigParser.RawConfigParser()
        config.read(path)
    except ConfigParser.Error as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return False

    conf_ctx = {} 
    
    try:
        conf_ctx['user'] = config.get('Database', 'user')
        conf_ctx['password'] = config.get('Database', 'password')
        conf_ctx['host'] = config.get('Database', 'host')
        conf_ctx['database'] = config.get('Database', 'database')
        conf_ctx['download'] = config.get('Common', 'download')    
    except ConfigParser.Error as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1])) 
        return False
 
    return conf_ctx 

def autoclick_db_connect(conf_ctx):
    global cursor, db

    try:
        db = MySQLdb.connect(host=conf_ctx['host'],
                            user=conf_ctx['user'],
                            passwd=conf_ctx['password'],
                            db=conf_ctx['database'],
                            charset='utf8',
                            use_unicode=True)
    except MySQLdb.Error as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return False
    
    cursor = db.cursor()

def autoclick_db_disconnect():
    global db, cursor
    db.close()
    
def autoclick_get_login_ctx(login_id):
    global cursor, db
   
    query = "SELECT * FROM account WHERE id=%s" % login_id
    
    try:
        cursor.execute(query)
        db.commit()
        rows = cursor.fetchall()
    except MySQLdb.Error as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return False
 
    login_ctx = {}
    login_ctx['id'] = login_id
    login_ctx['login'] = rows[0][1]
    login_ctx['password'] = rows[0][2] 
    login_ctx['resolution_w'], login_ctx['resolution_h'] = rows[0][3].split('x')
    login_ctx['campaign_name'] = rows[0][4]
    login_ctx['user_agent'] = rows[0][5]    
    login_ctx['download'] = ''
    login_ctx['proxy'] = ''

    return login_ctx

def autoclick_ya_set_price(campaign_id, price):
    global browser, logged_in
   
    if not logged_in:
        sys.stderr.write("error: you are logged in\n")
        return False
 
    try:
        campaign_xpath = '//a[contains(@href, ' + campaign_id + ') and contains(@href, showCamp)]'
        campaign = browser.find_element_by_xpath(campaign_xpath)
    except NoSuchElementException as err:
        return False
    
    main_window = browser.current_window_handle

    # open new tab
    browser.find_element_by_tag_name('body').send_keys(Keys.CONTROL + 't')
    campaign_link = campaign.get_attribute('href')
    browser.get(campaign_link)
     
    campaign_price = browser.find_element_by_xpath('//span[contains(text(), "Цены для всей кампании")]')   
    
    autoclick_sparse_click(campaign_price)
   
    time.sleep(2) 
 
    try: 
        price_window = browser.find_element_by_xpath('//div[contains(@class,"b-offline-set-phrases-prices__content_tab")]')
    except NoSuchElementException as err:
        return False
   
    try:
        common_price = price_window.find_element_by_xpath('.//span[contains(text(), "Единая цена")]')
        autoclick_sparse_click(common_price)
    except NoSuchElementException as err:
        return False

    time.sleep(2)
 
    try:
        price_set = price_window.find_element_by_xpath('.//button/span[contains(text(), "Установить")]')
        price_set_btn = price_set.find_element_by_xpath('..')
    except NoSuchElementException as err:
        return False
   
    try:
        price_cancel = price_window.find_element_by_xpath('.//button/span[contains(text(), "Отмена")]')
        price_cancel_btn = price_cancel.find_element_by_xpath('..')
    except NoSuchElementException as err:
        return False
 
    try:
        price_input = price_window.find_element_by_xpath('.//span/input')
    except NoSuchElementException as err:
        return False
    
    price_input.clear()
    price_input.send_keys(price)
    
    autoclick_sparse_click(price_set_btn)

    time.sleep(5)

    browser.find_element_by_tag_name('body').send_keys(Keys.ESCAPE)
    browser.find_element_by_tag_name('body').send_keys(Keys.CONTROL + 'w')
    browser.switch_to_window(main_window)

    return True

def autoclick_ya_stop_campaign(campaign_id):
    global browser, logged_in
   
    if not logged_in:
        sys.stderr.write("error: you are not logged in\n")
        return False
     
    try:
        campaign_stop_fmt = '//a[contains(text(), "Остановить") and contains(@href, ' + campaign_id + ')]'
        campaign_stop = browser.find_element_by_xpath(campaign_stop_fmt)
    except NoSuchElementException as err:
        return False

    autoclick_sparse_click(campaign_stop)

    return True

def autoclick_ya_start_campaign(campaign_id):
    global browser, logged_in

    if not logged_in:
        sys.stderr.write("error: you are not logged in\n")
        return False

    try:
        campaign_start_fmt = '//a[contains(text(), "Включить") and contains(@href, ' + campaign_id + ')]'
        campaign_start = browser.find_element_by_xpath(campaign_start_fmt)
    except NoSuchElementException as err:
        return False

    autoclick_sparse_click(campaign_start)

    return True

def autoclick_ya_get_money(ya_context):
    global browser, db, cursor, logged_in

    if not logged_in:
        sys.stderr.write("error: you are not logged in\n")
        return False

    try:
        wallet = browser.find_element_by_xpath('//div[@class="b-wallet-rest__total"]').text
        m = re.search("(^[0-9]+)\s*([0-9]+[.][0-9]*)", wallet.encode('ascii', 'ignore'))
        money = m.group(1) + m.group(2)
    except NoSuchElementException:
        money = "-"
  
    now = datetime.datetime.now()
    date = "%s-%s-%s" % (now.year, now.month, now.day)
    
    try:
        cursor.execute('''SELECT id from wallet WHERE id_company=%s AND date=%s''', (ya_context['id'], date)) 
        db.commit()
        records = cursor.fetchall()
    except MySQLdb.Error as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return False
 
    try:
        if len(records) == 0:
            cursor.execute('''INSERT INTO wallet (id_company, money, date) VALUES(%s, %s, %s)''', (ya_context['id'], money, date))
        else:
            cursor.execute('''UPDATE wallet SET money=%s WHERE id_company=%s AND date=%s''', (money, ya_context['id'], date))
        db.commit()
    except MySQLdb.Error as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return False

    return True

def autoclick_ya_download_statistics():
    global browser, db, cursor, logged_in

    ndownloads = 0
    main_window = browser.current_window_handle
     
    if not logged_in:
        sys.stderr.write("error: you are not logged in\n")
        return ndownloads

    try:
        stats = browser.find_elements_by_link_text('Статистика')
    except NoSuchElementException as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return ndownloads
    
    for stat in stats:
        stat_link = stat.get_attribute("href")
        
        try:
            browser.find_element_by_tag_name('body').send_keys(Keys.CONTROL + 't')
        except NoSuchElementException as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return ndownloads
    
        browser.get(stat_link)
   
        # today     
 
        try:
            autoclick_sparse_click(browser.find_element_by_xpath('//span[text() = "сегодня"]'))
            autoclick_sparse_click(browser.find_element_by_xpath('(//button[@type="button"])[3]'))
        except NoSuchElementException as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return ndownloads
 
        time.sleep(5)
    
        try:
            autoclick_sparse_click(browser.find_element_by_xpath('//div[@class="b-statistics-form__download-as-xls"]'))
            # autoclick_sparse_click(browser.find_element_by_xpath('//div/a/span'))
        except NoSuchElementException as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return ndownloads
        
        # yesterday
 
        try:
            autoclick_sparse_click(browser.find_element_by_xpath('//span[text() = "вчера"]'))
            autoclick_sparse_click(browser.find_element_by_xpath('(//button[@type="button"])[3]'))
        except NoSuchElementException as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return ndownloads
 
        time.sleep(5)
        
        try: 
            autoclick_sparse_click(browser.find_element_by_xpath('//div[@class="b-statistics-form__download-as-xls"]'))
            # autoclick_sparse_click(browser.find_element_by_xpath('//div/a/span'))
        except NoSuchElementException as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return ndownloads
        
        ndownloads += 2
        
        try: 
            browser.find_element_by_tag_name('body').send_keys(Keys.CONTROL + 'w')
        except NoSuchElementException as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return ndownloads
 
        browser.switch_to_window(main_window)
        
    return ndownloads

def autoclick_ya_download_statistics_all():
    global browser, db, cursor, logged_in

    ndownloads = 0
    main_window = browser.current_window_handle

    if not logged_in:
        sys.stderr.write("error: you are not logged in\n")
        return ndownloads
    
    try:       
        login_stat = browser.find_element_by_link_text('Статистика по всем кампаниям')
        login_stat_href = login_stat.get_attribute('href')
    except NoSuchElementException as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return ndownloads 

    try:
        browser.find_element_by_tag_name('body').send_keys(Keys.CONTROL + 't')
    except NoSuchElementException as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return ndownloads 
 
    browser.get(login_stat_href)

    # today 
    
    try:
        autoclick_sparse_click(browser.find_element_by_xpath('//span[text() = "сегодня"]'))
        autoclick_sparse_click(browser.find_element_by_xpath('(//button[@type="button"])[2]'))
    except NoSuchElementException as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return ndownloads 
 
    time.sleep(5)
  
    try:
        autoclick_sparse_click(browser.find_element_by_xpath('//div[@class="b-statistics-form__download-as-xls"]'))
        # autoclick_sparse_click(browser.find_element_by_xpath('//div/a/span'))
    except NoSuchElementException as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return ndownloads 
 
    ndownloads += 1

    # yesterday
  
    try:   
        autoclick_sparse_click(browser.find_element_by_xpath('//span[text() = "вчера"]'))
        autoclick_sparse_click(browser.find_element_by_xpath('(//button[@type="button"])[2]'))
    except NoSuchElementException as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return ndownloads 
 
    time.sleep(5)

    try:
        autoclick_sparse_click(browser.find_element_by_xpath('//div[@class="b-statistics-form__download-as-xls"]'))
        # autoclick_sparse_click(browser.find_element_by_xpath('//div/a/span'))
    except NoSuchElementException as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return ndownloads 

    ndownloads += 1 

    try: 
        browser.find_element_by_tag_name('body').send_keys(Keys.CONTROL + 'w')
    except NoSuchElementException as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return ndownloads 

    browser.switch_to_window(main_window)
  
    return ndownloads

def autoclick_db_set_price(login_id, campaign_id, price):
    global db, cursor, logged_in

    if not logged_in:
        sys.stderr.write("error: you are not logged in\n")
        return True
 
    table = "price"
    query_fmt = "SELECT * FROM %s WHERE login_id = \"%s\" AND company_id = \"%s\"" 
    query = query_fmt % (table, login_id, campaign_id)
   
    try:
        cursor.execute(query)
        db.commit()
        records = cursor.fetchall()
    except MySQLdb.Error as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return False
 
    if len(records) == 0:
        query_fmt = "INSERT INTO %s (login_id, company_id, price, stop) VALUES (%s, %s, %s, %s)"  
        query = query_fmt % (table, login_id, campaign_id, price, "0")
       
        try:
            cursor.execute(query)
            db.commit()
        except MySQLdb.Error as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return False
    else:
        query_fmt = "UPDATE %s SET price=%s WHERE login_id = \"%s\" AND company_id = \"%s\""
        query = query_fmt % (table, price, login_id, campaign_id)
       
        try:
            cursor.execute(query)
            db.commit()
        except MySQLdb.Error as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return False

    return True 
        
def autoclick_db_campaign_set(login_id, campaign_id, flag):
    global db, cursor, logged_in

    if not logged_in:
        sys.stderr.write("error: you are not logged in\n")
        return True
     
    table = "price"
    query_fmt = "SELECT * FROM %s WHERE login_id = \"%s\" AND company_id = \"%s\"" 
    query = query_fmt % (table, login_id, campaign_id)
  
    if flag == "stop":
        stop = "1"
    elif flag == "start":
        stop = "0"
     
    try:
        cursor.execute(query)
        db.commit()
        records = cursor.fetchall()
    except MySQLdb.Error as err:
        sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
        return False
  
    if len(records) == 0:
        query_fmt = "INSERT INTO %s (login_id, company_id, stop) VALUES (%s, %s, %s)"  
        query = query_fmt % (table, login_id, campaign_id, stop)
    
        try:
            cursor.execute(query)
            db.commit()
        except MySQLdb.Error as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return False
    else:
        query_fmt = "UPDATE %s SET stop=%s WHERE login_id = \"%s\" AND company_id = \"%s\""
        query = query_fmt % (table, stop, login_id, campaign_id)
       
        try:
            cursor.execute(query)
            db.commit()
        except MySQLdb.Error as err:
            sys.stderr.write("error %d %s\n" % (err.args[0], err.args[1]))
            return False
    
    return True
