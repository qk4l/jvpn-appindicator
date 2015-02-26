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
APP_NAME = 'jvpn-appindicator'
WORK_DIR = os.path.dirname(sys.argv[0]) + '/'
jvpn_dir = '/home/alexandrov/programs/jvpn/'
jvpn_icon = WORK_DIR + 'icons/junos-pulse.png'
jvpn_icon_bw = WORK_DIR + 'icons/junos-pulse_bw.png'


class JVPNIndicator:
    def __init__(self):
        # create an indicator applet
        self.ind = appindicator.Indicator('JVPN Tray', 'jvpn-status', appindicator.CATEGORY_APPLICATION_STATUS)
        self.ind.set_status(appindicator.STATUS_ACTIVE)
        self.ind.set_attention_icon(jvpn_icon)
        self.ind.set_icon(jvpn_icon_bw)
        self.keyring = Keyring()
        self.invalid_cred = False
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
        self.t_jvpn = JVPN(None, None)

    def update_status(self, msg):
        # Check status msg for future actions
        if msg.find('Invalid user') != -1:
            self.invalid_cred = True
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
        try:
            if self.t_jvpn.isAlive():
                self.t_jvpn.disconnect()
        except:
            pass
        gtk.main_quit()

    def connect(self, widget, data=None):
        # jvpn thread
        if not self.t_jvpn.isAlive():
            # Check if previous connection was failed because invalid creds
            if self.invalid_cred:
                self.invalid_cred = False
                login, password = self.keyring.newpass()
            else:
                login, password = self.keyring.getpass()
            self.t_jvpn = JVPN(login, password)
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
    def __init__(self, login, password):
        super(JVPN, self).__init__()
        self.jvpnpl = jvpn_dir + 'jvpn.pl'
        self.jvpnprocess = ''
        self.login = login
        self.password = password

    def connect(self):
        print('Connect process was called')

        if not self.password:
            msg = 'You didn`t provide password or it`s empty. Sorry, I can`t work in this way'
            show_notify(msg)
            update_status(msg)
            return ''
        try:
            self.jvpnprocess = subprocess.Popen([self.jvpnpl],
                                                cwd=jvpn_dir,
                                                stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE)
            self.jvpnprocess.stdin.write(self.login + '\n')
            self.jvpnprocess.stdin.write(self.password + '\n')
            lines_iterator = iter(self.jvpnprocess.stdout.readline, '')
            line = ''
            for line in lines_iterator:
                # line iterator thought jvpn.pl for communicate and parsing stdout
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
        print('end jvpn thread')


class Keyring():
    def __init__(self):
        self.keyring = gnomekeyring.get_default_keyring_sync()
        self.login = ''
        self.password = ''

    def getpass(self):
        try:
            result_list = gnomekeyring.find_items_sync(gnomekeyring.ITEM_GENERIC_SECRET, dict(appname=APP_NAME))
        except gnomekeyring.NoMatchError:
            # Create new credentials if nothing was found
            self.newpass()
        except BaseException as e:
            # Todo: add some logging
            pass
        else:
            self.login, self.password = result_list[0].secret.split('\n')
        return self.login, self.password

    def write2keyring(self):
        gnomekeyring.item_create_sync(
            self.keyring,
            gnomekeyring.ITEM_GENERIC_SECRET,
            APP_NAME,
            dict(appname=APP_NAME),
            "\n".join((self.login, self.password)), True)

    def newpass(self):
        dialog = gtk.Dialog("Credentials to Junos Pulse", None, 0,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                             gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.props.has_separator = False
        dialog.set_default_response(gtk.RESPONSE_OK)

        hbox = gtk.HBox(False, 8)
        hbox.set_border_width(8)
        dialog.vbox.pack_start(hbox, False, False, 0)

        stock = gtk.image_new_from_stock(gtk.STOCK_DIALOG_AUTHENTICATION,
                                         gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(stock, False, False, 0)

        table = gtk.Table(2, 3)
        table.set_row_spacings(5)
        table.set_col_spacings(5)
        hbox.pack_start(table, True, True, 0)

        label = gtk.Label("_Login")
        label.set_use_underline(True)
        table.attach(label, 0, 1, 0, 1)
        local_entry1 = gtk.Entry()
        local_entry1.set_text(self.login)
        local_entry1.set_activates_default(True)

        table.attach(local_entry1, 1, 2, 0, 1)
        label.set_mnemonic_widget(local_entry1)

        label = gtk.Label("_Password")
        label.set_use_underline(True)
        table.attach(label, 0, 1, 1, 2)
        local_entry2 = gtk.Entry()

        local_entry2.set_visibility(False)
        local_entry2.set_activates_default(True)

        table.attach(local_entry2, 1, 2, 1, 2)
        label.set_mnemonic_widget(local_entry2)

        savepass_btn = gtk.CheckButton('save password')
        table.attach(savepass_btn, 1, 2, 2, 3)

        dialog.show_all()
        while True:
            response = dialog.run()
            if response == gtk.RESPONSE_OK:
                self.login = local_entry1.get_text()
                self.password = local_entry2.get_text()
                if self.login and self.password:
                    if savepass_btn.get_active():
                        self.write2keyring()
                    break
            else:
                break
        dialog.destroy()
        return self.login, self.password


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