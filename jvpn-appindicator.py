#!/usr/bin/env python
import gtk
import gobject
import appindicator
import gnomekeyring
import pynotify
import threading
import re
import os
import subprocess
import time
import pygtk
pygtk.require('2.0')

"""
Appindicator that provide GUI interface to communicate with Junos Pulse.
jvpn-appindicator uses Gnome Keychain so you can be free to save credential with it
"""
__author__ = 'Artyom Alexandrov <qk4l()tem4uk.ru>'
__license__ = """The MIT License (MIT) Copyright (c) [2015] [Artyom Alexandrov]"""


gtk.gdk.threads_init()

# Config
APP_NAME = 'jvpn-appindicator'
WORK_DIR = os.path.dirname(os.path.realpath(__file__)) + '/'

pulse_dir = '/usr/local/pulse/'
pulseclient = pulse_dir + 'PulseClient.sh'
jvpn_icon = WORK_DIR + 'icons/junos-pulse.png'
jvpn_icon_bw = WORK_DIR + 'icons/junos-pulse_bw.png'
pulse_connected_pattern = 'Connection Status \:\n{2}\s*connection status : (\w+)\n\s*bytes sent \: (\d+)\n\s*bytes received \: (\d+)\n\s*Connection Mode : (\w+)\n\s+Encryption Type \: (.*)\n\s+Comp Type \: (\w+)\n\s+Assigned IP \: (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'


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
        self.status = gtk.MenuItem(pulse_status())
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

        # jvpn configure menu
        self.btnconfigure = gtk.MenuItem("Configure")
        self.btnconfigure.connect("activate", self.configure)
        self.btnconfigure.show()

        # jvpn disconnect menu
        self.btndisconnect = gtk.MenuItem("Disconnect")
        self.btndisconnect.connect("activate", self.disconect)

        if 'Connected' in pulse_status():
            self.switch_btn(True)

        # quit menu
        btnquit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        btnquit.connect("activate", self.quit)
        btnquit.show()
        self.menu.append(self.btnconnect)
        self.menu.append(self.btndisconnect)
        self.menu.append(self.btnconfigure)
        self.menu.append(btnquit)
        self.menu.show()
        self.ind.set_menu(self.menu)
        self.t_jvpn = Pulse(None, None, None, None)

    def update_status(self, msg):
        # Check status msg for future actions
        if msg.find('Login failed') != -1:
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
                self.t_jvpn.event.set()
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
                login, password, host, realm = self.keyring.newpass()
            else:
                login, password, host, realm = self.keyring.getpass()
            self.t_jvpn = Pulse(login, password, host, realm)
            # Start jvpn thread
            self.t_jvpn.start()
            self.switch_btn(True)

    def configure(self, widget, data=None):
        self.keyring.getpass()
        self.keyring.newpass()

    def disconect(self, widget, data=None):
        # Stop jvpn thread
        if self.t_jvpn.isAlive():
            self.t_jvpn.disconnect()
            self.switch_btn(False)
            status = pulse_status()
            update_status(status)
            show_notify(status)
        else:
            subprocess.Popen(['/bin/bash', pulseclient, '-K'],
                             cwd=pulse_dir)
            self.switch_btn(False)
            status = pulse_status()
            update_status(pulse_status())
            show_notify(status)

    def main(self):
        gtk.main()


class Pulse(threading.Thread):
    def __init__(self, login, password, host, realm):
        super(Pulse, self).__init__()
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.pulseprocess = ''
        self.login = login
        self.password = password
        self.host = host
        self.realm = realm

    @property
    def connect(self):
        print('Connect process was called')

        if not self.password:
            msg = 'You didn`t provide password or it`s empty. Sorry, I can`t work in this way'
            show_notify(msg)
            update_status(msg)
            return ''
        try:
            cur_status = pulse_status()
            self.pulseprocess = subprocess.Popen(
                ['/bin/bash', pulseclient, '-C', '-u', self.login, '-L', '2', '-h', self.host, '-r', self.realm],
                cwd=pulse_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE)
            self.pulseprocess.stdin.write(self.password + '\n')
            update_status('Connecting...')
            time.sleep(5)
            while not self.event.is_set():
                status = pulse_status()
                update_status(status)
                if not 'Connected' in cur_status and 'Connected' in status:
                    cur_status = status
                    show_notify(status)
                if 'Disconnected' in status:
                    self.event.set()
                time.sleep(10)
        except BaseException as e:
            print(e)
            status = str(e)
        update_status(status.strip())
        show_notify(status.strip())

    def disconnect(self):
        print('Disconnect process was called')
        subprocess.Popen(['/bin/bash', pulseclient, '-K'],
                                                  cwd=pulse_dir)

    def run(self):
        self.connect
        switch_btn(False)
        print('end jvpn thread')


class Keyring():
    def __init__(self):
        self.keyring = gnomekeyring.get_default_keyring_sync()
        self.login = ''
        self.password = ''
        self.host = ''
        self.realm = ''

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
            try:
                self.login, self.password, self.host, self.realm = result_list[0].secret.split('\n')
            except:
                pass
        return self.login, self.password, self.host, self.realm

    def write2keyring(self):
        gnomekeyring.item_create_sync(
            self.keyring,
            gnomekeyring.ITEM_GENERIC_SECRET,
            APP_NAME,
            dict(appname=APP_NAME),
            "\n".join((self.login, self.password, self.host, self.realm)), True)

    def newpass(self):
        dialog = gtk.Dialog("Credentials to Junos Pulse", None, 0,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                             gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.props.has_separator = False
        dialog.set_default_response(gtk.RESPONSE_OK)

        hbox = gtk.HBox(False, 10)
        hbox.set_border_width(10)
        dialog.vbox.pack_start(hbox, False, False, 0)

        stock = gtk.image_new_from_stock(gtk.STOCK_DIALOG_AUTHENTICATION,
                                         gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(stock, False, False, 0)

        table = gtk.Table(10, 5)
        table.set_row_spacings(5)
        table.set_col_spacings(5)
        hbox.pack_start(table, True, True, 0)

        label = gtk.Label("_Host")
        label.set_use_underline(True)
        table.attach(label, 0, 1, 0, 1)
        local_entry_host = gtk.Entry()
        local_entry_host.set_text(self.host)
        local_entry_host.set_activates_default(True)

        table.attach(local_entry_host, 1, 2, 0, 1)
        label.set_mnemonic_widget(local_entry_host)

        label = gtk.Label("_Realm")
        label.set_use_underline(True)
        table.attach(label, 0, 1, 1, 2)
        local_entry_realm = gtk.Entry()
        local_entry_realm.set_text(self.realm)
        local_entry_realm.set_activates_default(True)

        table.attach(local_entry_realm, 1, 2, 1, 2)
        label.set_mnemonic_widget(local_entry_realm)

        label = gtk.Label("_Login")
        label.set_use_underline(True)
        table.attach(label, 0, 1, 3, 4)
        local_entry1 = gtk.Entry()
        local_entry1.set_text(self.login)
        local_entry1.set_activates_default(True)

        table.attach(local_entry1, 1, 2, 3, 4)
        label.set_mnemonic_widget(local_entry1)

        label = gtk.Label("_Password")
        label.set_use_underline(True)
        table.attach(label, 0, 1, 5, 6)
        local_entry2 = gtk.Entry()

        local_entry2.set_visibility(False)
        local_entry2.set_activates_default(True)

        table.attach(local_entry2, 1, 2, 5, 6)
        label.set_mnemonic_widget(local_entry2)

        savepass_btn = gtk.CheckButton('save config')
        table.attach(savepass_btn, 1, 2, 7, 8)

        dialog.show_all()
        while True:
            response = dialog.run()
            if response == gtk.RESPONSE_OK:
                self.host = local_entry_host.get_text()
                self.realm = local_entry_realm.get_text()
                self.login = local_entry1.get_text()
                self.password = local_entry2.get_text()
                if self.login and self.password and self.host and self.realm:
                    if savepass_btn.get_active():
                        self.write2keyring()
                    break
            else:
                break
        dialog.destroy()
        return self.login, self.password, self.host, self.realm


def update_status(msg):
    gobject.idle_add(indicator.update_status, msg)


def switch_btn(status):
    gobject.idle_add(indicator.switch_btn, status)


def show_notify(msg):
    # Show notificathion by pynotify
    n = pynotify.Notification('JVPN', msg, 'file://' + jvpn_icon)
    n.set_urgency(pynotify.URGENCY_NORMAL)
    n.show()


def pulse_status():
    """
    Read status from pulse_status file
    :return:
    """
    file_path = os.path.expanduser("~") + '/.pulse_secure/pulse/.pulse_status'
    try:
        pulse_secure_dir = os.path.dirname(file_path)
        if not os.path.exists(pulse_secure_dir):
            os.makedirs(pulse_secure_dir)
        file = open(file_path, 'r')
        file_data = file.read()
        file.close()
        match = re.match(pulse_connected_pattern, file_data)
        if match:
            output = 'Status: {status}, IP: {ip} ({recived}/{sent} bytes)'.format(status=match.group(1),
                                                                                  ip=match.group(7),
                                                                                  sent=match.group(2),
                                                                                  recived=match.group(3))
        else:
            output = file_data
    except:
        output = 'Disconnected'
    return output.rstrip()


if __name__ == "__main__":
    indicator = JVPNIndicator()
    pynotify.init("JVPNIndicator")
    indicator.main()
