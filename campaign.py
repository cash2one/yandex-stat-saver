#!/usr/bin/env python 
# -*- coding: utf-8 -*-

import sys
import argparse
import autoclick2 as ac

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--proxy", action="store", dest="proxy", required=True, help="set proxy")
    parser.add_argument("--conf", action="store", dest="conf", required=True, help="set path to conf file")
    parser.add_argument("--id", action="store", dest="login_id", required=True, help="login id")
    parser.add_argument("--dir", action="store", dest="download", required=True, help="download dir")
    parser.add_argument("--campaign", action="store", dest="campaign_id", required=True, help="company id")
    parser.add_argument("--stop", action="store_true", dest="stop", default=False, help="stop a campaign")
    parser.add_argument("--start", action="store_true", dest="start", default=False, help="start a campaign")
    parser.add_argument("--price", action="store", dest="price", help="set a campaign price")
    
    args = parser.parse_args()

    proxy = args.proxy    
    conf = args.conf
    download = args.download
    campaign_id = args.campaign_id
    login_id = args.login_id
    
    conf_ctx = ac.autoclick_read_conf(conf)
    ac.autoclick_db_connect(conf_ctx)
    login_ctx = ac.autoclick_get_login_ctx(login_id)
    
    if login_ctx['proxy'] == '':
        login_ctx['proxy'] = proxy

    if login_ctx['download'] == '':
        login_ctx['download'] = download
    
    ac.autoclick_login_ya(login_ctx)
    
    if args.price:
        ac.autoclick_ya_set_price(campaign_id, args.price)
        ac.autoclick_db_set_price(login_id, campaign_id, args.price)
    
    if args.stop:
        ac.autoclick_ya_stop_campaign(campaign_id) 
        ac.autoclick_db_campaign_set(login_id, campaign_id, "stop")
    elif args.start:
        ac.autoclick_ya_start_campaign(campaign_id)
        ac.autoclick_db_campaign_set(login_id, campaign_id, "start")

    ac.autoclick_db_disconnect()
