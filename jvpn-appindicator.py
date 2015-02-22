#!/usr/bin/env python
"""
Appindicator that together with jvpn https://github.com/samm-git/jvpn allow you to connect to Juniper VPN.
jvpn-appindicator uses Gnome Keychain so you can be free to save credential with it
"""
__author__ = 'Artyom Alexandrov <qk4l()tem4uk.ru>'
__license__ = """The MIT License (MIT) Copyright (c) [2015] [Artyom Alexandrov]"""

import pygtk

pygtk.require('2.0')
import gtk
import gobject
import appindicator
import gnomekeyring
import pynotify
import threading
import os
import subprocess
import sys

gtk.gdk.threads_init()

# Config
WORK_DIR = os.path.dirname(sys.argv[0]) + '/'
jvpn_dir = '/home/alexandrov/programs/jvpn/'
jvpn_icon = WORK_DIR + 'icons/junos-pulse.png'
jvpn_icon_bw = WORK_DIR + 'icons/junos-pulse_bw.png'
print jvpn_icon

class JVPNIndicator:
    def __init__(self):
        # create an indicator applet
        self.ind = appindicator.Indicator('JVPN Tray', 'jvpn-status', appindicator.CATEGORY_APPLICATION_STATUS)
        self.ind.set_status(appindicator.STATUS_ACTIVE)
        self.ind.set_attention_icon(jvpn_icon)
        self.ind.set_icon(jvpn_icon_bw)
        # create a menu
        self.menu = gtk.Menu()
        # create items for the menu
        self.status = gtk.MenuItem('Not connected')
        self.status.show()
        self.menu.append(self.status)
        # A separator
        separator = gtk.SeparatorMenuItem()
        separator.show()
        self.menu.append(separator)
        # jvpn connect menu
        self.btnconnect = gtk.MenuItem("Connect")
        self.btnconnect.connect("activate", self.connect)
        self.btnconnect.show()
        # jvpn disconnect menu
        self.btndisconnect = gtk.MenuItem("Disconnect")
        self.btndisconnect.connect("activate", self.disconect)
        # quit menu
        btnquit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        btnquit.connect("activate", self.quit)
        btnquit.show()
        self.menu.append(self.btnconnect)
        self.menu.append(self.btndisconnect)
        self.menu.append(btnquit)
        self.menu.show()
        self.ind.set_menu(self.menu)
        # jvpn thread
        self.t_jvpn = JVPN()

    def update_status(self, msg):
        self.status.get_child().set_text(msg)

    def switch_btn(self, status):
        # Show or hide connect/disconnect btn depend on status
        if status:
            self.btnconnect.hide()
            self.btndisconnect.show()
            self.ind.set_status(appindicator.STATUS_ATTENTION)
        else:
            self.btnconnect.show()
            self.btndisconnect.hide()
            self.ind.set_status(appindicator.STATUS_ACTIVE)

    def quit(self, widget, data=None):
        # Close jvpn tread
        if self.t_jvpn.isAlive():
            self.t_jvpn.disconnect()
        gtk.main_quit()

    def connect(self, widget, data=None):
        if not self.t_jvpn.isAlive():
            self.t_jvpn = JVPN()
            # Start jvpn thread
            self.t_jvpn.start()
            self.switch_btn(True)

    def disconect(self, widget, data=None):
        # Stop jvpn thread
        if self.t_jvpn.isAlive():
            self.t_jvpn.disconnect()
            self.switch_btn(False)

    def main(self):
        gtk.main()


class JVPN(threading.Thread):
    def __init__(self):
        super(JVPN, self).__init__()
        self.jvpnpl = jvpn_dir + 'jvpn.pl'
        self.jvpnprocess = ''
        # TODO: Change it to use Gnome Keychain
        self.login = 'login'
        self.password = 'password'

    def connect(self):
        print('Connect process was called')
        try:
            self.jvpnprocess = subprocess.Popen([self.jvpnpl],
                                                cwd=jvpn_dir,
                                                stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE)
            self.jvpnprocess.stdin.write(self.password + '\n')
            lines_iterator = iter(self.jvpnprocess.stdout.readline, '')
            line = ''
            for line in lines_iterator:
                print line
                if line.startswith('Connected'):
                    update_status(line.split(',')[0])
                    show_notify(line.split(',')[0])
            if line.strip() == 'Exiting':
                line = 'Not connected'
        except BaseException as e:
            print(e)
            line = str(e)
        update_status('[JVPN] ' + line.strip())
        show_notify(line.strip())

    def disconnect(self):
        print('Disconnect process was called')
        self.jvpnprocess.terminate()

    def run(self):
        self.connect()
        switch_btn(False)
        #print 'end thread'


def update_status(msg):
    gobject.idle_add(indicator.update_status, msg)


def switch_btn(status):
    gobject.idle_add(indicator.switch_btn, status)


def show_notify(msg):
    # Show notificathion by pynotify
    n = pynotify.Notification('JVPN', msg, 'file://' + jvpn_icon)
    n.set_urgency(pynotify.URGENCY_NORMAL)
    n.show()


if __name__ == "__main__":
    indicator = JVPNIndicator()
    pynotify.init("JVPNIndicator")
    indicator.main()