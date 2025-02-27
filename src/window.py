import gatt
import configparser
import urllib.request
from pathlib import Path
from gi.repository import Gtk, GObject
from .bluetooth import InfiniTimeDevice
from .ble_dfu import InfiniTimeDFU
from .unpacker import Unpacker
from .quick_deploy import *


@Gtk.Template(resource_path="/org/gnome/siglo/window.ui")
class SigloWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "SigloWindow"
    info_scan_pass = Gtk.Template.Child()
    scan_fail_box = Gtk.Template.Child()
    scan_pass_box = Gtk.Template.Child()
    sync_time_button = Gtk.Template.Child()
    ota_picked_box = Gtk.Template.Child()
    ota_selection_box = Gtk.Template.Child()
    dfu_progress_box = Gtk.Template.Child()
    main_info = Gtk.Template.Child()
    bt_spinner = Gtk.Template.Child()
    dfu_progress_bar = Gtk.Template.Child()
    dfu_progress_text = Gtk.Template.Child()
    multi_device_listbox = Gtk.Template.Child()
    rescan_button = Gtk.Template.Child()
    multi_device_switch = Gtk.Template.Child()
    auto_bbox_scan_pass = Gtk.Template.Child()
    bbox_scan_pass = Gtk.Template.Child()
    ota_pick_tag_combobox = Gtk.Template.Child()
    ota_pick_asset_combobox = Gtk.Template.Child()
    ota_pick_asset_combobox = Gtk.Template.Child()
    deploy_type_switch = Gtk.Template.Child()

    def __init__(self, mode, deploy_type, **kwargs):
        self.ble_dfu = None
        self.ota_file = None
        self.manager = None
        self.asset = None
        self.asset_download_url = None
        self.tag = None
        self.mode = mode
        self.deploy_type = deploy_type
        super().__init__(**kwargs)
        GObject.threads_init()
        if mode == "multi":
            self.auto_switch_mode = True
            self.multi_device_switch.set_active(True)
        if deploy_type == "quick":
            self.full_list = get_quick_deploy_list()
        if deploy_type == "manual":
            self.auto_switch_deploy_type = True
            self.deploy_type_switch.set_active(True)

    def depopulate_listbox(self):
        children = self.multi_device_listbox.get_children()
        for child in children:
            self.multi_device_listbox.remove(child)
        self.multi_device_listbox.set_visible(False)

    def populate_listbox(self):
        for mac_addr in self.manager.device_set:
            label = Gtk.Label(xalign=0)
            label.set_use_markup(True)
            label.set_name("multi_mac_label")
            label.set_text(mac_addr)
            label.set_justify(Gtk.Justification.LEFT)
            self.multi_device_listbox.add(label)
            try:
                label.set_margin_start(10)
            except AttributeError:
                label.set_margin_left(10)
            label.set_width_chars(20)
            self.multi_device_listbox.set_visible(True)
            self.multi_device_listbox.show_all()

    def populate_tagbox(self):
        for tag in get_tags(self.full_list):
            self.ota_pick_tag_combobox.append_text(tag)

    def populate_assetbox(self):
        self.ota_pick_asset_combobox.remove_all()
        for asset in get_assets_by_tag(self.tag, self.full_list):
            self.ota_pick_asset_combobox.append_text(asset)

    def done_scanning_multi(self, manager, info_prefix):
        self.manager = manager
        scan_result = manager.get_scan_result()
        self.bt_spinner.set_visible(False)
        self.rescan_button.set_visible(True)
        info_suffix = "\n[INFO ] Multi-Device Mode"
        if scan_result:
            info_suffix += "\n[INFO ] Scan Succeeded"
            self.populate_listbox()
        else:
            info_suffix += "\n[INFO ] Scan Failed"
            self.scan_fail_box.set_visible(True)
        self.main_info.set_text(info_prefix + info_suffix)

    def done_scanning_singleton(self, manager, info_prefix):
        self.manager = manager
        scan_result = manager.get_scan_result()
        self.bt_spinner.set_visible(False)
        info_suffix = "\n[INFO ] Single-Device Mode"
        if scan_result:
            info_suffix += "\n[INFO ] Scan Succeeded"
            self.info_scan_pass.set_text(
                manager.alias
                + " Found!\n\nAdapter Name: "
                + manager.adapter_name
                + "\nMac Address: "
                + manager.get_mac_address()
            )
            self.scan_pass_box.set_visible(True)
            self.ota_picked_box.set_visible(True)
            if self.deploy_type == "quick":
                self.auto_bbox_scan_pass.set_visible(True)
                self.populate_tagbox()
            if self.deploy_type == "manual":
                self.bbox_scan_pass.set_visible(True)
        else:
            info_suffix += "\n[INFO ] Scan Failed"
            self.rescan_button.set_visible(True)
            self.scan_fail_box.set_visible(True)
        self.main_info.set_text(info_prefix + info_suffix)

    @Gtk.Template.Callback()
    def multi_listbox_row_selected(self, list_box, row):
        if row is not None:
            mac_add = row.get_child().get_label()
            self.manager.set_mac_address(mac_add)
            self.info_scan_pass.set_text(
                self.manager.alias
                + " Found!\n\nAdapter Name: "
                + self.manager.adapter_name
                + "\nMac Address: "
                + self.manager.get_mac_address()
            )
            print("deploy type!", self.deploy_type)
            self.scan_pass_box.set_visible(True)
            self.ota_picked_box.set_visible(True)
            if self.deploy_type == "manual":
                self.bbox_scan_pass.set_visible(True)
            if self.deploy_type == "quick":
                self.auto_bbox_scan_pass.set_visible(True)
                self.populate_tagbox()
            self.multi_device_listbox.set_visible(False)

    @Gtk.Template.Callback()
    def ota_pick_tag_combobox_changed_cb(self, widget):
        self.tag = self.ota_pick_tag_combobox.get_active_text()
        self.populate_assetbox()

    @Gtk.Template.Callback()
    def ota_pick_asset_combobox_changed_cb(self, widget):
        self.asset = self.ota_pick_asset_combobox.get_active_text()
        if self.asset is not None:
            self.ota_picked_box.set_sensitive(True)
            self.asset_download_url = get_download_url(
                self.asset, self.tag, self.full_list
            )
        else:
            self.ota_picked_box.set_sensitive(False)
            self.asset_download_url = None

    @Gtk.Template.Callback()
    def rescan_button_clicked(self, widget):
        if self.manager is not None:
            print("[INFO ] Rescan button clicked")
            self.depopulate_listbox()
            self.main_info.set_text("Rescanning...")
            self.bt_spinner.set_visible(True)
            self.scan_fail_box.set_visible(False)
            self.rescan_button.set_visible(False)
            self.scan_pass_box.set_visible(False)
            info_prefix = "[INFO ] Done Scanning"
            self.manager.scan_result = False
            try:
                self.manager.scan_for_infinitime()
            except gatt.errors.NotReady:
                info_prefix = "[WARN ] Bluetooth is disabled"
            if self.manager.mode == "singleton":
                self.done_scanning_singleton(self.manager, info_prefix)
            if self.manager.mode == "multi":
                self.done_scanning_multi(self.manager, info_prefix)

    @Gtk.Template.Callback()
    def sync_time_button_clicked(self, widget):
        if self.manager is not None:
            print("Sync Time button clicked...")
            device = InfiniTimeDevice(
                manager=self.manager, mac_address=self.manager.get_mac_address()
            )
            device.connect()
            self.main_info.set_text("InfiniTime Sync... Success!")
            self.scan_pass_box.set_visible(False)

    @Gtk.Template.Callback()
    def ota_file_selected(self, widget):
        filename = widget.get_filename()
        self.ota_file = filename
        self.main_info.set_text("File: " + filename.split("/")[-1])
        self.ota_picked_box.set_visible(True)
        self.ota_selection_box.set_visible(False)
        self.ota_picked_box.set_sensitive(True)

    @Gtk.Template.Callback()
    def ota_cancel_button_clicked(self, widget):
        if self.deploy_type == "quick":
            self.ota_pick_asset_combobox.remove_all()
            self.ota_pick_tag_combobox.remove_all()
            self.populate_tagbox()
            self.ota_picked_box.set_sensitive(False)
        if self.deploy_type == "manual":
            self.main_info.set_text("Choose another OTA File")
            self.ota_picked_box.set_visible(False)
            self.ota_selection_box.set_visible(True)

    @Gtk.Template.Callback()
    def flash_it_button_clicked(self, widget):
        if self.deploy_type == "quick":
            file_name = "/tmp/" + self.asset
            local_filename, headers = urllib.request.urlretrieve(
                self.asset_download_url, file_name
            )
            self.ota_file = local_filename

        self.main_info.set_text("Updating Firmware...")
        self.ota_picked_box.set_visible(False)
        self.dfu_progress_box.set_visible(True)
        self.sync_time_button.set_visible(False)
        self.auto_bbox_scan_pass.set_visible(False)
        unpacker = Unpacker()
        try:
            binfile, datfile = unpacker.unpack_zipfile(self.ota_file)
        except Exception as e:
            print("ERR")
            print(e)
            pass
        self.ble_dfu = InfiniTimeDFU(
            mac_address=self.manager.get_mac_address(),
            manager=self.manager,
            window=self,
            firmware_path=binfile,
            datfile_path=datfile,
            verbose=False,
        )
        self.ble_dfu.input_setup()
        self.dfu_progress_text.set_text(self.get_prog_text())
        self.ble_dfu.connect()

    @Gtk.Template.Callback()
    def deploy_type_toggled(self, widget):
        if self.deploy_type == "manual" and self.auto_switch_deploy_type:
            self.auto_switch_deploy_type = False
        else:
            current_deploy_type = self.deploy_type
            config = configparser.ConfigParser()
            home = str(Path.home())
            configDir = home + "/.config/siglo"
            configFile = configDir + "/siglo.ini"
            if current_deploy_type == "quick":
                config["settings"] = {"mode": self.mode, "deploy_type": "manual"}
                self.deploy_type = "manual"
            if current_deploy_type == "manual":
                config["settings"] = {"mode": self.mode, "deploy_type": "quick"}
                self.deploy_type = "quick"
            with open(configFile, "w") as f:
                config.write(f)
            self.main_info.set_text("[WARN ] Settings changed, please restart Siglo")
            self.rescan_button.set_visible(False)
            self.scan_pass_box.set_visible(False)
            self.depopulate_listbox()
            self.scan_fail_box.set_visible(False)
            self.auto_bbox_scan_pass.set_visible(False)

    @Gtk.Template.Callback()
    def mode_toggled(self, widget):
        if self.mode == "multi" and self.auto_switch_mode == True:
            self.auto_switch_mode = False
        else:
            current_mode = self.mode
            config = configparser.ConfigParser()
            home = str(Path.home())
            configDir = home + "/.config/siglo"
            configFile = configDir + "/siglo.ini"
            if current_mode == "singleton":
                config["settings"] = {"mode": "multi", "deploy_type": self.deploy_type}
                self.mode = "multi"
            if current_mode == "multi":
                config["settings"] = {"mode": "singleton", "deploy_type": self.deploy_type}
                self.mode = "singleton"
            with open(configFile, "w") as f:
                config.write(f)
            self.main_info.set_text("[WARN ] Settings changed, please restart Siglo")
            self.rescan_button.set_visible(False)
            self.scan_pass_box.set_visible(False)
            self.depopulate_listbox()
            self.scan_fail_box.set_visible(False)

    def update_progress_bar(self):
        self.dfu_progress_bar.set_fraction(
            self.ble_dfu.total_receipt_size / self.ble_dfu.image_size
        )
        self.dfu_progress_text.set_text(self.get_prog_text())

    def get_prog_text(self):
        return (
            str(self.ble_dfu.total_receipt_size)
            + " / "
            + str(self.ble_dfu.image_size)
            + " bytes recieved"
        )

    def show_complete(self):
        self.main_info.set_text("OTA Update Complete")
        self.bt_spinner.set_visible(False)
        self.sync_time_button.set_visible(True)
        self.dfu_progress_box.set_visible(False)
        if (self.deploy_type == "quick"):
            self.auto_bbox_scan_pass.set_visible(True)
