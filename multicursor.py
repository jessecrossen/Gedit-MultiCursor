from gi.repository import GObject, Gtk, Gdk, Gedit

class MultiCursor(GObject.Object, Gedit.ViewActivatable):
  __gtype_name__ = "MultiCursor"
  view = GObject.property(type=Gedit.View)
  
  def __init__(self):
    GObject.Object.__init__(self)
    self._handlers = [ ]
    self._handling = False
    self._scheduled = [ ]
    # a list of cursors besides the document cursor
    self.cursors = [ ]
    # a list of tags around all instances of the matched selection text
    self.matches = [ ]
    # map keyboard shortcuts
    self.keymap = {
      '<Control>d': self.match_cursor,
      '<Control>u': self.unmatch_cursor,
      'Escape': self.clear_cursors
    }
    self.compile_keymap()

  # parse and cache accelerators for the main key bindings
  def compile_keymap(self):
    new_keymap = { }
    for (combo, action) in self.keymap.items():
      accel = Gtk.accelerator_parse(combo)
      new_keymap[accel] = { 
        'accel': accel,
        'action': action
      }
    self.keymap = new_keymap
  
  # hook and unhook from view events
  def do_activate(self):
    # retain a reference to the document
    self.doc = self.view.get_buffer()
    # bind events
    self.add_handler(self.view, 'event', self.on_event)
    self.add_handler(self.view, 'move-cursor', self.mc_move_cursor)
  def do_deactivate(self):
    self.remove_handlers()

  # receive events from the document that control multiple cursors
  def hook_document(self):
    self.add_handler(self.doc, 'delete-range', self.schedule_delete)
    self.add_handler(self.doc, 'insert-text', self.schedule_insert)
    self.add_handler(self.doc, 'end-user-action', self.apply_scheduled)
  # stop receiving events from the document when there are no extra cursors
  def unhook_document(self):
    self.remove_handlers(self.doc)

  # add a signal handler for the given object
  def add_handler(self, obj, signal, handler):
    self._handlers.append((obj, obj.connect(signal, handler)))
  # remove handlers for the given object, 
  #  or all handlers if no object is passed
  def remove_handlers(self, remove_obj=None):
    kept = [ ]
    for (obj, handler_id) in self._handlers:
      if ((remove_obj is None) or (remove_obj == obj)):
        obj.disconnect(handler_id)
      else:
        kept.append((obj, handler_id))
    self._handlers = kept

  def on_event(self, view, event):
    if event.type == Gdk.EventType.KEY_PRESS:
      return self.on_key_press(view, event)
    elif event.type == Gdk.EventType.BUTTON_PRESS:
      if (event.get_state()[1] & Gdk.ModifierType.CONTROL_MASK):
        (b, x, y) = event.get_coords()
        (x, y) = view.window_to_buffer_coords(Gtk.TextWindowType.TEXT, x, y)
        (pos, b) = view.get_iter_at_position(x, y)
        self.add_cursor(pos, pos)
        return(True)
      else:
        self.clear_cursors()
    return False

  def on_key_press(self, view, event):
    keyval = Gdk.keyval_to_lower(event.keyval)
    mask = Gtk.accelerator_get_default_mod_mask() & event.state
    for shortcut in self.keymap.values():
      if ((shortcut['accel'][0] == keyval) and 
          (shortcut['accel'][1] == mask)):
        shortcut['action']()
        return(True)
    return(False)

  def order_iters(self, iters):
    if (iters[0].get_offset() <= iters[1].get_offset()):
      return(iters)
    else:
      return((iters[1], iters[0]))

  def get_selection_iters(self):
    start = self.doc.get_iter_at_mark(self.doc.get_insert())
    end = self.doc.get_iter_at_mark(self.doc.get_selection_bound())
    return((start, end))
    
  def match_cursor(self):
    (start, end) = self.order_iters(self.get_selection_iters())
    text = self.doc.get_text(start, end, True)
    if (len(text) == 0):
      return
    if (len(self.cursors) > 0):
      search_start = self.cursors[-1].get_end_iter()
    else:
      self.tag_all_matches(text)
      search_start = end
    if (search_start.get_offset() < start.get_offset()):
      search_end = start
    else:
      search_end = None
    match = self.get_next_match(text, search_start, search_end)
    # wrap around
    if ((match is None) and (search_start.get_offset() > end.get_offset())):
      search_end = start
      search_start = doc.get_start_iter()
      match = self.get_next_match(text, search_start, search_end)
    if (match is not None):
      self.add_cursor(match[0], match[1])
      self.cursors[-1].scroll_onscreen()
  
  def tag_all_matches(self, text):
    (sel_start, sel_end) = self.order_iters(self.get_selection_iters())
    start_iter = self.doc.get_start_iter()
    while (True):
      match = self.get_next_match(text, start_iter, None)
      if (match is None):
        break
      start_iter = match[1]
      # don't tag the selection
      if (match[0].get_offset() == sel_start.get_offset()):
        continue
      self.matches.append(MarkTag(self.view, 'multicursor_match', match[0], match[1]))
  
  def clear_matches(self):
    for match in self.matches:
      match.remove()
    self.matches = [ ]

  def get_next_match(self, text, search_start, search_end):
    return(search_start.forward_search(text, 0, search_end))
  
  def unmatch_cursor(self):
    self.remove_cursor(-1)
    # scroll back to the last cursor, or the selection
    if (len(self.cursors) > 0):
      self.cursors[-1].scroll_onscreen()
    else:
      self.view.scroll_mark_onscreen(self.doc.get_insert())
  
  def add_cursor(self, start_iter, end_iter):
    if (len(self.cursors) == 0):
      self.hook_document()
    self.cursors.append(Cursor(self.view, start_iter, end_iter))

  def remove_cursor(self, index):
    if (len(self.cursors) > 0):
      self.cursors[index].remove()
      del self.cursors[index]
      if (len(self.cursors) == 0):
        self.unhook_document()

  def clear_cursors(self):
    if (len(self.cursors) > 0):
      while (len(self.cursors) > 0):
        self.remove_cursor(-1)
      self.clear_matches()
  
  # schedule a multicursor insert for when the user's action is done
  def schedule_insert(self, doc, start, text, length):
    # get the offset from the insertion point
    (sel_start, sel_end) = self.order_iters(self.get_selection_iters())
    start_delta = start.get_offset() - sel_start.get_offset()
    # schedule this for when the user action is done
    self.schedule(self.mc_insert, (start_delta, text))

  # schedule a multicursor delete for when the user's action is done
  def schedule_delete(self, doc, start, end):
    # get the offset of the range from the insertion point
    (start, end) = self.order_iters((start, end))
    (sel_start, sel_end) = self.order_iters(self.get_selection_iters())
    start_delta = start.get_offset() - sel_start.get_offset()
    end_delta = end.get_offset() - sel_end.get_offset()
    # schedule this for when the user action is done
    self.schedule(self.mc_delete, (start_delta, end_delta))

  # schedule a function to be run when apply_scheduled is called
  def schedule(self, action, args):
    if (self._handling): return
    self._scheduled.append((action, args))
  # run scheduled functions
  def apply_scheduled(self, doc):
    if (self._handling): return
    self._handling = True
    # remove all match previews now that the user is doing something
    self.clear_matches()
    # execute the scheduled actions
    self.doc.begin_user_action()
    for (action, args) in self._scheduled:
      action(*args)
    self.doc.end_user_action()
    self._handling = False
    self._scheduled = [ ]

  # insert text at every cursor
  def mc_insert(self, start_delta, text):
    for cursor in self.cursors:
      cursor.insert(start_delta, text)

  # delete text at every cursor
  def mc_delete(self, start_delta, end_delta):
    # do the delete relative to all cursors
    for cursor in self.cursors:
      cursor.delete(start_delta, end_delta)

  def mc_move_cursor(self, view, step_size, count, extend_selection):
    # remove all match previews now that the user is doing something
    self.clear_matches()
    # clear all cursors if the movement would put them all in the same place
    if ((step_size == Gtk.MovementStep.BUFFER_ENDS) or
        (step_size == Gtk.MovementStep.PAGES)):
      self.clear_cursors()
      return
    for cursor in self.cursors:
      cursor.move(step_size, count, extend_selection)





# this class manages a single extra cursor in the document
class Cursor:

  def __init__(self, view, start_iter, end_iter):
    # hook to the document
    self.view = view
    self.doc = self.view.get_buffer()
    # add marks for the cursor and selection area
    self.tag = MarkTag(self.view, 'multicursor', start_iter, end_iter)

  # get an iter at the beginning of the selected area
  def get_start_iter(self):
    return(self.doc.get_iter_at_mark(self.tag.start_mark))

  # get an iter at the end of the selected area
  def get_end_iter(self):
    return(self.doc.get_iter_at_mark(self.tag.end_mark))

  # get the length between the start and end
  def get_length(self):
    return(self.get_end_iter().get_offset() - 
           self.get_start_iter().get_offset())

  # scroll so that this cursor is on-screen
  def scroll_onscreen(self):
    self.view.scroll_mark_onscreen(self.tag.end_mark)

  # remove the cursor from the document
  def remove(self):
    self.tag.remove()

  # insert text at the cursor
  def insert(self, start_delta, text):
    start_iter = self.doc.get_iter_at_offset(
      self.get_start_iter().get_offset() + start_delta)
    self.doc.insert(start_iter, text)

  # delete text at the cursor
  def delete(self, start_delta, end_delta):
    # apply deltas
    start_iter = self.doc.get_iter_at_offset(
      self.get_start_iter().get_offset() + start_delta)
    end_iter = self.doc.get_iter_at_offset(
      self.get_end_iter().get_offset() + end_delta)
    # see if the length of the selection is going to zero, in which case
    #  we need to adjust the tag and marks below
    had_length = (self.get_length() > 0)
    # delete the text
    self.doc.delete(start_iter, end_iter)
    # update the tag and marks if needed
    if ((self.get_length() > 0) != had_length):
      self.tag.do_move_marks()

  # move the cursor
  def move(self, step_size, count, extend_selection):
    start_iter = self.get_start_iter()
    end_iter = self.get_end_iter()
    # extend the selection if needed
    if (extend_selection):
      sel_start = self.doc.get_iter_at_mark(self.doc.get_insert())
      sel_end = self.doc.get_iter_at_mark(self.doc.get_selection_bound())
      sel_delta = sel_start.get_offset() - sel_end.get_offset()
      move_end = (count > 0)
      if (sel_delta != 0):
        move_end = (sel_delta > 0)
      if (move_end):
        self.move_iter(end_iter, step_size, count)
      else:
        self.move_iter(start_iter, step_size, count)
    # collapse the selection if there is one and the insertion point moves
    elif (end_iter.get_offset() != start_iter.get_offset()):
      if (count < 0):
        end_iter = start_iter.copy()
      else:
        start_iter = end_iter.copy()
    else:
      self.move_iter(start_iter, step_size, count)
      self.move_iter(end_iter, step_size, count)
    # update the tag
    self.tag.move_marks(start_iter, end_iter)

  # move an iter according to the kind of params we get from a 
  #  'cursor-move' signal from the view
  def move_iter(self, pos, step_size, count):
    if ((step_size == Gtk.MovementStep.LOGICAL_POSITIONS) or
        (step_size == Gtk.MovementStep.VISUAL_POSITIONS)):
      if (count < 0):
        pos.backward_chars(abs(count))
      else:
        pos.forward_chars(abs(count))
    elif (step_size == Gtk.MovementStep.WORDS):
      if (count < 0):
        pos.backward_word_starts(abs(count))
      else:
        pos.forward_word_ends(abs(count))
    elif (step_size == Gtk.MovementStep.DISPLAY_LINES):
      offset = pos.get_line_offset()
      if (count < 0):
        pos.backward_visible_lines(abs(count))
      else:
        pos.forward_visible_lines(abs(count))
      pos.set_line_offset(offset)
    elif (step_size == Gtk.MovementStep.PARAGRAPHS):
      if (count < 0):
        pos.backward_visible_lines(abs(count))
        pos.set_line_offset(0)
      else:
        pos.forward_visible_lines(abs(count))
        pos.forward_to_line_end()
    elif ((step_size == Gtk.MovementStep.HORIZONTAL_PAGES) or 
          (step_size == Gtk.MovementStep.DISPLAY_LINE_ENDS)):
      if (count < 0):
        pos.set_line_offset(0)
      else:
        pos.forward_to_line_end()




# this class manages a GtkTextTag, anchoring it with GtkTextMarks instead of GtkTextIters
class MarkTag:

  def __init__(self, view, name, start_iter, end_iter):
    self.view = view
    self.doc = self.view.get_buffer()
    self.name = name
    self.start_mark = self.doc.create_mark(None, start_iter, False)
    self.end_mark = self.doc.create_mark(None, end_iter, False)
    # update the tag for its initial position
    self.do_move_marks()

  # move the start and end marks to the specified locations, doing nothing
  #  if the locations are not changing
  def move_marks(self, new_start_iter=None, new_end_iter=None):
    start_iter = self.doc.get_iter_at_mark(self.start_mark)
    end_iter = self.doc.get_iter_at_mark(self.end_mark)
    if (((new_start_iter is not None) and 
         (new_start_iter.get_offset() != start_iter.get_offset())) or
        ((new_end_iter is not None) and 
         (new_end_iter.get_offset() != end_iter.get_offset()))):
      self.do_move_marks(new_start_iter, new_end_iter)
  # update the tag to reflect the new locations
  def do_move_marks(self, new_start_iter=None, new_end_iter=None):
    self.remove_tag()
    if (new_start_iter is not None):
      self.doc.move_mark(self.start_mark, new_start_iter)
    if (new_end_iter is not None):
      self.doc.move_mark(self.end_mark, new_end_iter)
    # show a mark if there is no selection
    start_iter = self.doc.get_iter_at_mark(self.start_mark)
    end_iter = self.doc.get_iter_at_mark(self.end_mark)
    if (start_iter.get_offset() != end_iter.get_offset()):
      self.add_tag()
      # make sure the start mark has left gravity so it tracks the 
      #  edge of the tag
      if (not self.start_mark.get_left_gravity()):
        self.doc.delete_mark(self.start_mark)
        self.start_mark = self.doc.create_mark(None, start_iter, True)
      self.start_mark.set_visible(False)
    else:
      # make sure the start mark has right gravity so text will be inserted
      #  before it
      if (self.start_mark.get_left_gravity()):
        self.doc.delete_mark(self.start_mark)
        self.start_mark = self.doc.create_mark(None, start_iter, False)
      self.start_mark.set_visible(True)

  # remove the tag and marks from the document
  def remove(self):
    self.start_mark.set_visible(False)
    self.remove_tag()
    self.doc.delete_mark(self.start_mark)
    self.doc.delete_mark(self.end_mark)

  # add a tag between the marks
  def add_tag(self):
    tag = self.get_tag()
    start_iter = self.doc.get_iter_at_mark(self.start_mark)
    end_iter = self.doc.get_iter_at_mark(self.end_mark)
    self.doc.apply_tag(tag, start_iter, end_iter)

  # remove the tag from between the marks if there is one
  def remove_tag(self):
    if (self.doc.get_tag_table().lookup(self.name) is not None):
      start_iter = self.doc.get_iter_at_mark(self.start_mark)
      end_iter = self.doc.get_iter_at_mark(self.end_mark)
      self.doc.remove_tag_by_name(self.name, start_iter, end_iter)

  # get a styled tag to place between the marks
  def get_tag(self):
    tag = self.doc.get_tag_table().lookup(self.name)
    if (tag is None):
      # style the selection part of a cursor
      if (self.name == 'multicursor'):
        background = self.get_view_color('selected_bg_color')
        foreground = self.get_view_color('selected_fg_color')
        (background, foreground) = self.get_scheme_colors( 
          'selection', (background, foreground))
      # style a preview of a match to the selection
      elif (self.name == 'multicursor_match'):
        background = '#FFFF00'
        foreground = self.get_view_color('text_color')
        (background, foreground) = self.get_scheme_colors(
          'search-match', (background, foreground))
      # this shouldn't happen, but make it obvious just in case
      else:
        background = '#FF0000'
        foreground = '#FFFFFF'
      tag = self.doc.create_tag(self.name, 
        background=background, 
        foreground=foreground)
    return(tag)

  # get the default color for the given style property of the view
  def get_view_color(self, color_name):
    return(self.view.get_style().lookup_color(color_name)[1].to_string())
  
  # get the given foreground and background colors from the current 
  #  style scheme, falling back on the given defaults
  def get_scheme_colors(self, style_name, defaults):
    scheme = self.doc.get_style_scheme()
    if (scheme is not None):
      sel_style = scheme.get_style(style_name)
      if (sel_style is not None):
        return(sel_style.get_property('background'), 
               sel_style.get_property('foreground'))
    return(defaults)