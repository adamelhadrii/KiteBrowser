"""The Settings dialog. Every row writes straight to SettingsManager; the app listens and re-applies instantly."""
import json
import os

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

import shortcuts
import themes
from settings import (CHOICES, DEFAULTS, ENGINES, TOOLBAR_BUTTONS, ZOOM_LEVELS, toolbar_layout, valid, valid_groups,
                      valid_keywords)

PAGE_ICONS = {"General": "go-home-symbolic", "Colors": "preferences-color-symbolic",
              "Look": "preferences-desktop-appearance-symbolic",
              "Start page": "user-home-symbolic", "Web": "web-browser-symbolic",
              "Privacy": "security-high-symbolic", "Shortcuts": "input-keyboard-symbolic"}

LABELS = {
    "theme_preset": themes.LABELS,
    "search_engine": {k: v[0] for k, v in ENGINES.items()},
    "tab_position": {"start": "Left (or top)", "end": "Right (or bottom)"},
    "close_buttons": {"hover": "When pointing at a tab", "always": "Always", "never": "Never"},
    "new_tab_page": {"start": "Kite start page", "homepage": "Homepage", "blank": "Blank page"},
    "new_tab_position": {"end": "At the end", "after": "Next to the current tab"},
    "last_tab": {"close": "Closes the window", "keep": "Keeps the window open"},
    "start_background": {"sky": "Sky (follows the theme)", "solid": "Solid color", "image": "Image"},
    "user_agent": {"default": "Kite (WebKit)", "firefox": "Firefox", "chrome": "Chrome", "safari": "Safari (Mac)",
                   "custom": "Custom"},
    "default_zoom": {z: f"{round(z * 100)}%" for z in ZOOM_LEVELS},
    "chrome_background": {"color": "Theme color", "gradient": "Gradient", "image": "Image"},
    "active_tab_style": {"bar": "Side bar", "fill": "Filled with the accent", "underline": "Underline",
                         "outline": "Outline"},
}


def open_settings_dialog(parent, app):
    s = app.s
    dialog = Adw.PreferencesDialog(title="Settings", search_enabled=True)
    pages, groups = {}, {}

    def toast(text):
        dialog.add_toast(Adw.Toast(title=text, timeout=4))

    def group(page, title, description=""):
        if page not in pages:
            pages[page] = Adw.PreferencesPage(title=page, name=page, icon_name=PAGE_ICONS[page])
            dialog.add(pages[page])
        if (page, title) not in groups:
            groups[page, title] = Adw.PreferencesGroup(title=title, description=description)
            pages[page].add(groups[page, title])
        return groups[page, title]

    def add(page, title, row):
        group(page, title).add(row)
        return row

    def switch(page, grp, key, title, subtitle=""):
        row = Adw.SwitchRow(title=title, subtitle=subtitle, active=s[key])
        row.connect("notify::active", lambda r, _: s.set(key, r.get_active()))
        return add(page, grp, row)

    def combo(page, grp, key, title, subtitle=""):
        opts, labels = CHOICES[key], LABELS.get(key, {})
        row = Adw.ComboRow(title=title, subtitle=subtitle,
                           model=Gtk.StringList.new([labels.get(o, str(o).title()) for o in opts]))
        row.set_selected(opts.index(s[key]))  # after the model: setting a model resets the selection to the first item
        row.connect("notify::selected", lambda r, _: s.set(key, opts[r.get_selected()]))
        return add(page, grp, row)

    def entry(page, grp, key, title):
        row = Adw.EntryRow(title=title, text=s[key], show_apply_button=True)

        def applied(r):
            value = r.get_text().strip() or DEFAULTS[key]
            if key == "homepage" and "://" not in value and not value.startswith(("kite:", "about:")):
                value = "https://" + value
            if not valid(key, value):
                toast("Use a web address starting with https://" + (" that contains {}" if key == "search_url" else ""))
                return
            r.set_text(value)
            s.set(key, value)

        row.connect("apply", applied)
        return add(page, grp, row)

    def spin(page, grp, key, title, step=1, subtitle=""):
        from settings import RANGES
        lo, hi = RANGES[key]
        row = Adw.SpinRow.new_with_range(lo, hi, step)
        row.set_title(title)
        row.set_subtitle(subtitle)
        row.set_value(s[key])
        row.connect("notify::value", lambda r, _: s.set(key, int(r.get_value())))
        return add(page, grp, row)

    def suffix_button(row, icon, tip, callback):
        b = Gtk.Button(icon_name=icon, tooltip_text=tip, valign=Gtk.Align.CENTER)
        b.add_css_class("flat")
        b.connect("clicked", lambda *_: callback())
        row.add_suffix(b)
        return b

    def color(page, grp, key, title, subtitle="", fallback=None):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        rgba = Gdk.RGBA()
        if not (s[key] and rgba.parse(s[key])):
            if fallback:
                rgba = fallback()
            else:
                rgba.parse(DEFAULTS[key])
        picker = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False), rgba=rgba, valign=Gtk.Align.CENTER)
        picker.connect("notify::rgba", lambda b, _: s.set(key, "#%02x%02x%02x" % tuple(
            round(c * 255) for c in (b.get_rgba().red, b.get_rgba().green, b.get_rgba().blue))))

        def reset():
            if not DEFAULTS[key]:  # an empty default means "automatic", which no color button can show
                s.set(key, "")
                return
            default = Gdk.RGBA()
            default.parse(DEFAULTS[key])
            picker.set_rgba(default)  # fires notify::rgba, which saves it

        row.add_suffix(picker)
        suffix_button(row, "edit-undo-symbolic", "Reset", reset)
        return add(page, grp, row)

    def font(page, grp, key, title, subtitle, family_only):
        # A plain button rather than Gtk.FontDialogButton, which shows some font even when none is set.
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        button = Gtk.Button(label=s[key] or "Default", valign=Gtk.Align.CENTER)

        def pick(*_):
            def done(d, result):
                try:
                    chosen = d.choose_family_finish(result) if family_only else d.choose_font_finish(result)
                except GLib.Error:
                    return  # cancelled
                value = chosen.get_name() if family_only else chosen.to_string()
                s.set(key, value)
                button.set_label(value)

            current = Pango.FontDescription.from_string(s[key]) if s[key] and not family_only else None
            dialog_ = Gtk.FontDialog(title=title)
            if family_only:
                dialog_.choose_family(parent, None, None, done)
            else:
                dialog_.choose_font(parent, current, None, done)

        button.connect("clicked", pick)
        row.add_suffix(button)
        row.set_activatable_widget(button)

        def reset():
            s.set(key, "")
            button.set_label("Default")

        suffix_button(row, "edit-undo-symbolic", "Use the default font", reset)
        return add(page, grp, row)

    def choose_file(title, patterns, done):
        files = Gtk.FileFilter(name=title)
        for p in patterns:
            files.add_suffix(p)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(files)
        fd = Gtk.FileDialog(title=title, filters=store)

        def finished(d, result):
            try:
                done(d.open_finish(result).get_path())
            except GLib.Error:
                pass  # cancelled

        fd.open(parent, None, finished)

    # ---- General ------------------------------------------------------------
    combo("General", "Search", "search_engine", "Search engine",
          "Brave Search showed no ads or browser-install banners on results in testing")
    custom = entry("General", "Search", "search_url", "Custom search URL, with {} for the query")
    custom.set_visible(s["search_engine"] == "custom")
    # shortcut: this listener outlives the dialog (one per open); harmless, the row stays referenced
    s.connect(lambda key: key == "search_engine" and custom.set_visible(s["search_engine"] == "custom"))

    kw_group = group("General", "Search keywords",
                     "Type a keyword before your search, like “w kite” to search Wikipedia for kite.")
    kw_rows = []
    new_kw = [Adw.EntryRow(title=t) for t in ("Keyword, like w", "Name, like Wikipedia",
                                               "Search URL with {} for the query")]
    adder = Adw.ExpanderRow(title="Add a keyword")
    for r in new_kw:
        adder.add_row(r)
    add_button = Adw.ButtonRow(title="Add keyword")
    adder.add_row(add_button)

    def fill_keywords():
        for r in kw_rows:
            kw_group.remove(r)
        kw_rows.clear()
        for kw, name, url in valid_keywords(s["keywords"]):
            row = Adw.ActionRow(title=f"{kw}   {name}", subtitle=url, use_markup=False)
            suffix_button(row, "user-trash-symbolic", f"Remove {kw}", lambda k=kw: (
                s.set("keywords", [r for r in valid_keywords(s["keywords"]) if r[0] != k]), fill_keywords()))
            kw_group.add(row)
            kw_rows.append(row)
        kw_group.remove(adder)
        kw_group.add(adder)

    def add_keyword(*_):
        row = [r.get_text().strip() for r in new_kw]
        if not valid_keywords([row]):
            toast("Use a keyword without spaces and a web address that contains {}")
            return
        s.set("keywords", [r for r in valid_keywords(s["keywords"]) if r[0] != row[0]] + [row])
        for r in new_kw:
            r.set_text("")
        fill_keywords()

    add_button.connect("activated", add_keyword)
    kw_group.add(adder)
    fill_keywords()

    combo("General", "Tabs", "new_tab_page", "New tabs open")
    combo("General", "Tabs", "new_tab_position", "New tabs go")
    switch("General", "Tabs", "switch_to_new_tabs", "Switch to links opened in new tabs",
           "Off: Ctrl+click and middle-click open tabs in the background")
    combo("General", "Tabs", "last_tab", "Closing the last tab")
    switch("General", "Tabs", "restore_session", "Reopen tabs from last time")
    switch("General", "Tabs", "tab_sleep", "Enable Automatic Tab Sleeping", "Unloads background tabs to free memory")
    spin("General", "Tabs", "sleep_minutes", "Sleep after (minutes)")
    switch("General", "Tabs", "sleep_on_low_memory", "Sleep tabs early when memory runs low",
           "Below 12% free memory, the least recently used background tabs sleep first")
    switch("General", "Tools", "command_palette", "Command palette",
           "One search box for tabs, actions, settings, bookmarks and history")
    switch("General", "Tools", "split_view", "Split view",
           "Two tabs side by side, from a tab's menu or the split view shortcut")
    switch("General", "Tools", "site_panel", "Site panel from the padlock",
           "Connection, tracker blocking, zoom, permissions and data for the current site")
    switch("General", "Tools", "focus_mode", "Focus mode", "Hides the toolbar and tabs until you point at the top edge")
    switch("General", "Tools", "screenshot_full_page", "Screenshots capture the whole page",
           "Off: only the part you can see")
    entry("General", "Tools", "screenshot_dir", "Save screenshots to (empty = Pictures folder)")
    entry("General", "Start and downloads", "homepage", "Homepage (kite://start is the built-in page)")
    entry("General", "Start and downloads", "download_dir", "Save downloads to (empty = Downloads folder)")

    def export_settings():
        def finished(d, result):
            try:
                path = d.save_finish(result).get_path()
            except GLib.Error:
                return
            with open(path, "w") as f:
                json.dump(s.data, f, indent=2)
            toast(f"Settings exported to {os.path.basename(path)}")

        Gtk.FileDialog(title="Export settings", initial_name="kite-settings.json").save(parent, None, finished)

    def replaced(backup, rejected, verb):
        dialog.close()  # every row now shows stale values
        note = f" Skipped {len(rejected)} invalid entries." if rejected else ""
        parent.toast(f"Settings {verb}.{note}" + (f" Previous settings saved to {backup}" if backup else ""))

    def import_settings(path):
        try:
            with open(path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError
        except (OSError, ValueError):
            toast("That file isn't a Kite settings file")
            return
        replaced(*s.replace_all(data), "imported")

    def reset_settings():
        alert = Adw.AlertDialog(heading="Reset all settings?",
                                body="Every setting, including shortcuts and keywords, goes back to its default. "
                                     "Your current settings are saved to settings.json.bak first.")
        alert.add_response("cancel", "Cancel")
        alert.add_response("reset", "Reset")
        alert.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_close_response("cancel")
        alert.connect("response", lambda _a, r: r == "reset" and replaced(*s.replace_all({}, keep_paths=False), "reset"))
        alert.present(dialog)

    for title, callback in (("Export settings…", export_settings),
                            ("Import settings…", lambda: choose_file("Kite settings", ["json"], import_settings)),
                            ("Reset all settings…", reset_settings)):
        button = Adw.ButtonRow(title=title)
        button.connect("activated", lambda *_, cb=callback: cb())
        add("General", "Backup", button)

    # ---- Colors -------------------------------------------------------------
    preset = combo("Colors", "Theme", "theme_preset", "Color theme")
    scheme = combo("Colors", "Theme", "theme", "Light or dark")
    color("Colors", "Theme", "accent", "Accent color", "Reset returns to Kite saffron",
          lambda: Adw.StyleManager.get_default().get_accent_color_rgba())

    custom_rows = [
        color("Colors", "Your colors", "custom_window", "Window", "Behind the toolbar and tab panel"),
        color("Colors", "Your colors", "custom_view", "Page card", "Shown while a page loads, and around it"),
        color("Colors", "Your colors", "custom_popover", "Menus and dialogs"),
        color("Colors", "Your colors", "custom_text", "Text", "Reset to pick it automatically for contrast"),
    ]
    custom_group = group("Colors", "Your colors", "Used by the Custom theme. Its window color also decides light "
                                                  "or dark for buttons, switches and scrollbars.")

    def preset_changed(key):
        if key not in (None, "theme_preset"):
            return
        custom = s["theme_preset"] == "custom"
        custom_group.set_visible(custom)
        scheme.set_sensitive(not custom)
        scheme.set_subtitle("The Custom theme follows its window color" if custom else "")

    def seed_custom(_row, _pspec):
        # First time on Custom: start from the theme being left, so nothing jumps.
        keys = ("custom_window", "custom_view", "custom_popover")
        if s["theme_preset"] == "custom" and all(s[k] == DEFAULTS[k] for k in keys) and previous[0] != "custom":
            p = themes.PRESETS[previous[0]][Adw.StyleManager.get_default().get_dark()]
            for k, slot in zip(keys, ("window", "view", "popover")):
                s.set(k, p[slot])
            dialog.close()  # the color buttons show the old values; reopen to see the seeded ones
            parent.toast("Custom theme started from your previous colors. Open Settings to fine-tune them.")
        previous[0] = s["theme_preset"]

    previous = [s["theme_preset"]]
    preset.connect("notify::selected", seed_custom)
    s.connect(preset_changed)  # shortcut: one listener per dialog open; harmless
    preset_changed(None)

    combo("Colors", "Window background", "chrome_background", "Background",
          "Behind the toolbar and tab panel; pages stay on their own card")
    color("Colors", "Window background", "chrome_gradient", "Gradient's second color")
    chrome_image = add("Colors", "Window background", Adw.ActionRow(
        title="Image", subtitle=os.path.basename(s["chrome_image"]) or "None chosen", use_markup=False))

    def set_chrome_image(path):
        s.set("chrome_image", path)
        s.set("chrome_background", "image")
        chrome_image.set_subtitle(os.path.basename(path))

    suffix_button(chrome_image, "folder-open-symbolic", "Choose an image",
                  lambda: choose_file("Images", ["png", "jpg", "jpeg", "webp", "gif"], set_chrome_image))
    spin("Colors", "Window background", "chrome_dim", "Dim the image (%)", step=5,
         subtitle="Lays the window color over the image so text stays readable")
    spin("Colors", "Window background", "chrome_opacity", "Window opacity (%)", step=5,
         subtitle="Lets your desktop show through. Adds to Hyprland's own window opacity.")

    for name, key in themes.GROUP_COLOR_KEYS.items():
        color("Colors", "Tab group colors", key, name)

    reset_colors = add("Colors", "Start over", Adw.ButtonRow(title="Reset colors and background"))

    def reset_color_section(*_):
        for key in ("theme_preset", "theme", "accent", "custom_window", "custom_view", "custom_popover", "custom_text",
                    "chrome_background", "chrome_gradient", "chrome_dim", "chrome_opacity",
                    *themes.GROUP_COLOR_KEYS.values()):
            s.set(key, DEFAULTS[key])
        dialog.close()
        parent.toast("Colors and background reset")

    reset_colors.connect("activated", reset_color_section)

    # ---- Look ---------------------------------------------------------------
    spin("Look", "Shape and size", "roundness", "Corner roundness (px)", subtitle="0 is square")
    spin("Look", "Shape and size", "card_gap", "Space around pages (px)", subtitle="0 lets pages fill the window")
    spin("Look", "Shape and size", "card_border", "Page outline (px)")
    switch("Look", "Shape and size", "card_shadow", "Shadow under pages")
    spin("Look", "Shape and size", "toolbar_height", "Toolbar height (px)", step=2)
    font("Look", "Shape and size", "ui_font", "Interface font", "The system font", family_only=False)
    combo("Look", "Shape and size", "density", "Tab spacing")
    switch("Look", "Shape and size", "animations", "Animations",
           "Kite's own transitions and the drifting kite on the start page")

    combo("Look", "Tab panel", "tab_layout", "Tab layout")
    combo("Look", "Tab panel", "tab_position", "Tab panel position")
    switch("Look", "Tab panel", "show_tabs", "Show Tab Panel", "The tab panel toggle button and shortcut also hide it")
    switch("Look", "Tab panel", "show_brand", "Show the Kite logo in the panel")
    spin("Look", "Tab panel", "sidebar_width", "Sidebar width (px)", step=10)
    spin("Look", "Tab panel", "tab_width", "Tab width in horizontal layout (px)", step=10)
    combo("Look", "Tab panel", "close_buttons", "Close buttons on tabs", "Middle-click or Ctrl+W always close a tab")
    switch("Look", "Tab panel", "show_favicons", "Site icons on tabs")
    switch("Look", "Tab panel", "auto_group", "Enable Smart Tab Auto-Grouping", "Development, Social, Research, Media")
    switch("Look", "Tab panel", "tab_search", "Show Tab Strip Search Bar")
    combo("Look", "Tab panel", "active_tab_style", "Current tab looks like")

    groups_box = group("Look", "Tab groups", "Your own groups come first. A domain also matches its subdomains, "
                                             "so example.com covers docs.example.com.")
    switch("Look", "Tab groups", "builtin_groups", "Built-in groups", "Development, Social, Research and Media")
    group_rows = []
    new_group = [Adw.EntryRow(title="Group name, like Work"),
                 Adw.EntryRow(title="Domains, like jira.example.com, slack.com")]
    group_adder = Adw.ExpanderRow(title="Add a group")
    for r in new_group:
        group_adder.add_row(r)
    add_group_button = Adw.ButtonRow(title="Add group")
    group_adder.add_row(add_group_button)

    def fill_groups():
        for r in group_rows:
            groups_box.remove(r)
        group_rows.clear()
        for name, domains in valid_groups(s["group_rules"]):
            row = Adw.ActionRow(title=name, subtitle=", ".join(domains), use_markup=False)
            suffix_button(row, "user-trash-symbolic", f"Remove {name}", lambda n=name: (
                s.set("group_rules", [[g, ", ".join(d)] for g, d in valid_groups(s["group_rules"]) if g != n]),
                fill_groups()))
            groups_box.add(row)
            group_rows.append(row)
        groups_box.remove(group_adder)
        groups_box.add(group_adder)

    def add_group(*_):
        name, domains = (r.get_text().strip() for r in new_group)
        parsed = valid_groups([[name, domains]])
        if not parsed:
            toast("Give the group a name and at least one domain, like example.com")
            return
        rows = [[g, ", ".join(d)] for g, d in valid_groups(s["group_rules"]) if g != name]
        s.set("group_rules", rows + [[parsed[0][0], ", ".join(parsed[0][1])]])
        for r in new_group:
            r.set_text("")
        fill_groups()

    add_group_button.connect("activated", add_group)
    groups_box.add(group_adder)
    fill_groups()

    switch("Look", "Address bar", "show_url", "Address bar")
    switch("Look", "Address bar", "show_reader", "Reader view button")
    switch("Look", "Address bar", "suggestions", "Suggestions while typing", "From your bookmarks and history")

    toolbar = group("Look", "Toolbar", "Show, hide and reorder buttons. The menu button always stays, so Settings "
                                       "is always within reach.")
    tool_rows = []

    def fill_toolbar():
        for r in tool_rows:
            toolbar.remove(r)
        tool_rows.clear()
        start, end = toolbar_layout(s)
        for side, names in (("start", start), ("end", end)):
            for i, name in enumerate(names):
                label, show_key = TOOLBAR_BUTTONS[name]
                row = Adw.ActionRow(title=label, subtitle="Left side" if side == "start" else "Right side")
                suffix_button(row, "go-previous-symbolic", "Move left", lambda n=name: move(n, -1)).set_sensitive(i > 0)
                suffix_button(row, "go-next-symbolic", "Move right", lambda n=name: move(n, 1)).set_sensitive(
                    i < len(names) - 1)
                suffix_button(row, "object-flip-horizontal-symbolic", "Move to the other side", lambda n=name: swap(n))
                toggle = Gtk.Switch(active=s[show_key], valign=Gtk.Align.CENTER)
                toggle.connect("notify::active", lambda w, _, k=show_key: (
                    s.set(k, w.get_active()), GLib.idle_add(fill_toolbar)))  # back and forward share a switch
                row.add_suffix(toggle)
                toolbar.add(row)
                tool_rows.append(row)
        return GLib.SOURCE_REMOVE

    def store_layout(start, end):
        s.set("toolbar_start", start)
        s.set("toolbar_end", end)
        fill_toolbar()

    def move(name, step):
        start, end = toolbar_layout(s)
        side = start if name in start else end
        i = side.index(name)
        side[i], side[i + step] = side[i + step], side[i]
        store_layout(start, end)

    def swap(name):
        start, end = toolbar_layout(s)
        if name in start:
            start.remove(name)
            end.insert(0, name)
        else:
            end.remove(name)
            start.append(name)
        store_layout(start, end)

    fill_toolbar()

    # ---- Start page ---------------------------------------------------------
    combo("Start page", "Background", "start_background", "Background")
    color("Start page", "Background", "start_color", "Solid color", "Used when the background is a solid color")
    image = add("Start page", "Background", Adw.ActionRow(
        title="Image", subtitle=os.path.basename(s["start_image"]) or "None chosen", use_markup=False))

    def set_image(path):
        s.set("start_image", path)
        s.set("start_background", "image")
        image.set_subtitle(os.path.basename(path))

    suffix_button(image, "folder-open-symbolic", "Choose an image",
                  lambda: choose_file("Images", ["png", "jpg", "jpeg", "webp", "gif"], set_image))
    switch("Start page", "Show", "start_show_kite", "Kite and its string")
    switch("Start page", "Show", "start_clock", "Clock")
    switch("Start page", "Show", "start_show_search", "Search box")
    switch("Start page", "Show", "start_show_bookmarks", "Bookmarks")
    switch("Start page", "Show", "start_show_recent", "Recently visited sites", "Needs Memory Finder turned on")
    spin("Start page", "Show", "start_tiles", "Sites per section")

    # ---- Web ----------------------------------------------------------------
    font("Web", "Fonts", "font_sans", "Sans-serif font", "Used by most pages", family_only=True)
    font("Web", "Fonts", "font_serif", "Serif font", "Used by pages that ask for serif", family_only=True)
    font("Web", "Fonts", "font_mono", "Monospace font", "Used for code", family_only=True)
    spin("Web", "Fonts", "font_size", "Default text size (px)")
    spin("Web", "Fonts", "font_size_mono", "Code text size (px)")
    spin("Web", "Fonts", "min_font_size", "Minimum text size (px)", subtitle="0 lets pages decide")
    combo("Web", "Pages", "default_zoom", "Default zoom", "Sites you zoom yourself keep their own level")
    combo("Web", "Pages", "user_agent", "Identify as",
          "Applies to new page loads. Some sites misbehave when this doesn't match the real browser.")
    ua = entry("Web", "Pages", "user_agent_custom", "Custom user agent")
    ua.set_visible(s["user_agent"] == "custom")
    s.connect(lambda key: key == "user_agent" and ua.set_visible(s["user_agent"] == "custom"))
    switch("Web", "Pages", "block_autoplay", "Block autoplay with sound", "Applies to new tabs")
    switch("Web", "Pages", "javascript", "JavaScript", "Most sites need it")
    switch("Web", "Pages", "smooth_scrolling", "Smooth scrolling")
    switch("Web", "Pages", "spell_check", "Check spelling in text fields")
    switch("Web", "Pages", "devtools", "Developer tools", "The WebKit inspector, from the menu or its shortcut")

    files = group("Web", "Your files", f"Plain files in {app.user_files.folder}. Kite reloads them when you save.")
    for name, key, title, subtitle in (
        ("interface.css", "use_interface_css", "Interface CSS", "Restyles Kite itself"),
        ("userstyle.css", "use_user_styles", "Page CSS", "Added to every web page"),
        ("userscript.js", "use_user_script", "Page script", "Runs on every web page; applies on the next page load"),
    ):
        row = Adw.SwitchRow(title=title, subtitle=f"{subtitle} ({name})", active=s[key])
        row.connect("notify::active", lambda r, _, k=key: s.set(k, r.get_active()))
        suffix_button(row, "document-edit-symbolic", f"Edit {name}", lambda n=name: Gtk.FileLauncher(
            file=Gio.File.new_for_path(app.user_files.ensure(n))).launch(parent, None, None))
        files.add(row)
    folder = Adw.ButtonRow(title="Open the folder")
    folder.connect("activated", lambda *_: Gtk.FileLauncher(
        file=Gio.File.new_for_path(app.user_files.folder)).launch(parent, None, None))
    files.add(folder)

    # ---- Privacy ------------------------------------------------------------
    switch("Privacy", "Tracking", "block_trackers", "Block trackers and ad networks",
           "Built-in list of about 70 analytics, ad and social-pixel domains")
    switch("Privacy", "Tracking", "itp", "Intelligent tracking prevention", "Limits cross-site cookies used to follow you")
    switch("Privacy", "Memory Finder", "memory_search", "Enable Natural Language Memory Search",
           "Indexes visited pages on this computer only, to search them by description")
    clear = add("Privacy", "Clear data", Adw.ButtonRow(title="Clear history, cookies and site data"))
    clear.add_css_class("destructive-action")

    def confirm_clear(*_):
        alert = Adw.AlertDialog(heading="Clear browsing data?", body=(
            "This deletes your history, the Memory Finder index, cookies and saved site data. "
            "You'll be signed out of websites. This can't be undone."))
        alert.add_response("cancel", "Cancel")
        alert.add_response("clear", "Clear data")
        alert.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_close_response("cancel")
        alert.connect("response", lambda _a, r: r == "clear" and app.clear_data(toast))
        alert.present(dialog)

    clear.connect("activated", confirm_clear)

    # ---- Shortcuts ----------------------------------------------------------
    shortcut_rows = []

    def fill_shortcuts():
        for grp, row in shortcut_rows:
            grp.remove(row)
        shortcut_rows.clear()
        current = shortcuts.effective(s["shortcuts"])
        for section, name, title, _defaults in shortcuts.ACTIONS:
            grp = group("Shortcuts", section)
            row = Adw.ActionRow(title=title, activatable=True)
            row.add_suffix(Gtk.ShortcutLabel(accelerator=current[name][0] if current[name] else "",
                                             disabled_text="Off", valign=Gtk.Align.CENTER))
            if name in s["shortcuts"]:
                suffix_button(row, "edit-undo-symbolic", "Back to the default", lambda n=name: (
                    s.set("shortcuts", {k: v for k, v in s["shortcuts"].items() if k != n}), fill_shortcuts()))
            row.connect("activated", lambda _r, n=name: capture(n))
            grp.add(row)
            shortcut_rows.append((grp, row))
        reset_row = Adw.ButtonRow(title="Reset all shortcuts")
        reset_row.connect("activated", lambda *_: (s.set("shortcuts", {}), fill_shortcuts()))
        group("Shortcuts", "Reset").add(reset_row)
        shortcut_rows.append((group("Shortcuts", "Reset"), reset_row))

    def capture(name):
        prompt = Gtk.Label(label=f"Press the new shortcut for “{shortcuts.TITLES[name]}”", wrap=True)
        prompt.add_css_class("title-4")
        hint = Gtk.Label(label="Esc cancels. Backspace turns this shortcut off.")
        hint.add_css_class("dim-label")
        error = Gtk.Label(wrap=True)
        error.add_css_class("error")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=24, margin_bottom=24,
                      margin_start=24, margin_end=24)
        for w in (prompt, hint, error):
            box.append(w)
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(Adw.HeaderBar())
        cap = Adw.Dialog(title="Change shortcut", child=view, content_width=440)

        def apply(accel):
            try:
                new, taken = shortcuts.rebind(s["shortcuts"], name, accel)
            except ValueError as e:
                error.set_label(str(e))
                return
            s.set("shortcuts", new)
            cap.close()
            fill_shortcuts()
            if taken:
                toast(f"Also removed from: {', '.join(taken)}")

        def pressed(_ctl, keyval, _code, state):
            if Gdk.KEY_Shift_L <= keyval <= Gdk.KEY_Hyper_R or keyval == Gdk.KEY_ISO_Level3_Shift:
                return True  # a modifier on its own: wait for the real key
            mods = state & Gtk.accelerator_get_default_mod_mask()
            if keyval == Gdk.KEY_Escape and not mods:
                cap.close()
            elif keyval == Gdk.KEY_BackSpace and not mods:
                apply(None)
            else:
                apply(Gtk.accelerator_name(Gdk.keyval_to_lower(keyval), mods))
            return True

        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", pressed)
        cap.add_controller(keys)
        app.suspend_shortcuts(True)  # otherwise pressing Ctrl+T here would open a tab instead of recording it
        cap.connect("closed", lambda *_: app.suspend_shortcuts(False))
        cap.present(dialog)

    fill_shortcuts()
    dialog.present(parent)
    return dialog
