#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import getopt
import autoclick2 as ac

if __name__ == "__main__":
    
    try:
        opts, args = getopt.getopt(sys.argv[1:], "p:", [ "proxy=", "conf=", "id=",  "dir="])
    except getopt.GetoptError as err:
        sys.stderr.write("error: %d %s\n" % (err.args[0], err.args[1]))
        sys.exit(1)
   
    for o, a in opts:
        if o in ("-p", "--proxy"):
            proxy = a
        elif o in ("--conf"):
            conf = a
        elif o in ("--id"):
            login_id = a  
        elif o in ("--dir"):
            download = a
        else:
            assert False, "unhandled option"

    conf_ctx = ac.autoclick_read_conf(conf)
    ac.autoclick_db_connect(conf_ctx)
    login_ctx = ac.autoclick_get_login_ctx(login_id)

    if login_ctx['proxy'] == '':
        login_ctx['proxy'] = proxy

    if login_ctx['download'] == '':
        login_ctx['download'] = download

    ac.autoclick_login_ya(login_ctx)
    ac.autoclick_ya_get_money(login_ctx)
        
    n = 0
    n += ac.autoclick_ya_download_statistics()
    n += ac.autoclick_ya_download_statistics_all()
    
    ac.autoclick_db_disconnect()

    print n
