Gedit-MultiCursor
=================

A plugin for gedit 3+ that adds multiple cursor support as popularized by [Sublime Text](http://www.sublimetext.com/). Not all features are implemented yet, see below for details about what is and isn't supported.

Installing
==========

1. clone the repo:

        git clone https://github.com/jessecrossen/Gedit-MultiCursor.git
        cd Gedit-MultiCursor
        ./install.sh
    
    or unpack a snapshot if don't use git:

        wget https://github.com/jessecrossen/Gedit-MultiCursor/archive/master.zip
        unzip master.zip
        cd Gedit-MultiCursor-master
        ./install.sh

2. restart gedit from the console

3. enable the MultiCursor plugin in the preferences dialog.

4. If you see something like this in your console output:

        (gedit:4579): libpeas-WARNING **: Could not find loader 'python3' for plugin 'multicursor'
    
    Edit the second line of multicursor.plugin to read as follows:

        Loader=python
    
    Then re-run install.sh and try again from there.

Usage
=====

You can add a cursor by selecting some text and using the **Control-d** shortcut. All instances of that text will be highlighted, and the next one will get a cursor around it. Use **Control-u** to remove the last cursor you added. Start typing, move the cursor, or delete to modify the text at all the current cursors.

If you want to match the selection without case sensitivity, use **Control-Shift-d**. If the selected text is keyword-like (made up of alphanumerics, dashes, and underscores), this will also enable fuzzy matching, where "myVariable" will match "MY_VARIABLE", "my-variable", and so on. When you start typing, any cursors that matched text with a different casing convention will retain that casing convention as much as possible for whatever text you enter. This makes it easy to quickly refactor a bunch of related keywords, like a constant, a private variable, and a property that all refer to the same thing.

Use **Control-Up** and **Control-Down** to select text above and below the current selection. This allows you to quickly select text in columns, like tabular data or repetitive lines of code.

You can also add cursors anywhere by clicking while holding down the **Control** key (not working on all systems).

If you have different text selected with multiple cursors, you can use cut/copy/paste and each cursor will maintain its own clipboard, which can be used along with cursor movement commands (like Control-Left, Control-Right, Home, End, and so on) to do some fairly complex refactoring jobs.

Use **Escape** or click anywhere to return to just the normal cursor.

Configuration
=============

There's no configuration UI yet, but it would be great if someone handier than me with Gtk would write one! Sorry if you liked using **Control-d** to delete a line, but it should be pretty easy to change if you want to. You can change the keyboard shortcuts by editing the strings at the top of multicursor.py.

Shortcomings
============

* As mentioned above, there's not an easy way to configure the plugin.
* The extra cursors don't blink like the main one. Maybe it's a feature?


