"""MindmapTab — XMind-style canvas with nodes, edges, zoom/pan/drag."""
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pomodoro_common import load, save, node_edge_points, move_children


class MindmapTab(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.mindmap_selected = None
        self.mindmap_selected_edge = None
        self.mindmap_connecting = None
        self.mindmap_drag = None
        self.mindmap_pan_mode = False
        self.mindmap_pan_start = None
        self.mindmap_nodes = []
        self.mindmap_edges = []
        self.mindmap_data = []
        self.mindmap_current = None
        self.mindmap_scale = 1.0
        self.mindmap_offset_x = 0
        self.mindmap_offset_y = 0
        self._mindmap_active = None
        self._build()

    def _build(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(toolbar, text='Mindmap:', font=('SF Pro Text', 9, 'bold')).pack(side='left', padx=(0, 4))
        self.mindmap_var = tk.StringVar()
        self.mindmap_cb = ttk.Combobox(toolbar, textvariable=self.mindmap_var, width=20, state='readonly')
        self.mindmap_cb.pack(side='left', padx=4)
        self.mindmap_cb.bind('<<ComboboxSelected>>', self._on_mindmap_selected)
        ttk.Button(toolbar, text='+', style='Primary.TButton', command=self._add_mindmap).pack(side='left', padx=2)
        ttk.Button(toolbar, text='-', style='Danger.TButton', command=self._remove_mindmap).pack(side='left', padx=2)

        ttk.Separator(toolbar, orient='vertical').pack(side='left', padx=8, fill='y')

        self.mindmap_toolbar = ttk.Frame(toolbar)
        self.mindmap_toolbar.pack(side='left', padx=4)
        ttk.Button(self.mindmap_toolbar, text='Topic', style='Card.TButton', command=self._add_topic).pack(side='left', padx=2)
        ttk.Button(self.mindmap_toolbar, text='Subtopic', style='Card.TButton', command=self._add_subtopic_prompt).pack(side='left', padx=2)
        ttk.Button(self.mindmap_toolbar, text='Relationship', style='Card.TButton', command=self._add_relationship).pack(side='left', padx=2)
        ttk.Button(self.mindmap_toolbar, text='Delete', style='Danger.TButton', command=self._delete_selected).pack(side='left', padx=2)

        self.mindmap_zoom_label = ttk.Label(toolbar, text='100%', font=('SF Pro Text', 8))
        self.mindmap_zoom_label.pack(side='right', padx=4)
        ttk.Button(toolbar, text='Fit', style='Card.TButton', command=self._fit_view).pack(side='right', padx=4)
        ttk.Label(toolbar, text='Thickness:', font=('SF Pro Text', 8)).pack(side='right', padx=(8, 0))
        self._thick_var = tk.DoubleVar(value=2)
        sb_thick = ttk.Scale(toolbar, from_=1, to=5, variable=self._thick_var, orient='horizontal', length=60)
        sb_thick.pack(side='right', padx=4)
        sb_thick.bind('<ButtonRelease-1>', lambda e: self._draw())
        self.mindmap_thickness_var = self._thick_var

        self.mindmap_canvas = tk.Canvas(self, bg='#ffffff', borderwidth=0, highlightthickness=0, cursor='crosshair')
        sb_v = ttk.Scrollbar(self, orient='vertical', command=self.mindmap_canvas.yview)
        sb_h = ttk.Scrollbar(self, orient='horizontal', command=self.mindmap_canvas.xview)
        self.mindmap_canvas.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        self.mindmap_canvas.pack(side='left', fill='both', expand=True, padx=(8, 0), pady=4)
        sb_v.pack(side='right', fill='y', padx=(0, 4), pady=4)
        sb_h.pack(side='bottom', fill='x', padx=8, pady=(0, 4))

        self.mindmap_canvas.bind('<Double-Button-1>', lambda e: self._add_topic(e))
        self.mindmap_canvas.bind('<Button-3>', self._right_click)
        self.mindmap_canvas.bind('<Button-2>', self._right_click)
        self.mindmap_canvas.bind('<MouseWheel>', self._mousewheel)
        self.mindmap_canvas.bind('<Button-4>', lambda e: self._zoom(1.1))
        self.mindmap_canvas.bind('<Button-5>', lambda e: self._zoom(0.9))
        self.bind_all('<KeyPress-space>', self._space_press)
        self.bind_all('<KeyRelease-space>', self._space_release)
        self.mindmap_canvas.bind('<Button-1>', self._canvas_click)
        self.mindmap_canvas.bind('<B1-Motion>', self._canvas_drag)
        self.mindmap_canvas.bind('<ButtonRelease-1>', self._canvas_release)

        self._refresh_mindmaps()

    def _refresh_mindmaps(self):
        data = load()
        self.mindmap_data = data.get('mindmaps', [])
        names = [m['name'] for m in self.mindmap_data]
        self.mindmap_cb['values'] = names
        if self.mindmap_data and not self.mindmap_current:
            self.mindmap_current = self.mindmap_data[0]['id']
            self.mindmap_var.set(self.mindmap_data[0]['name'])
        self._draw()

    def _add_mindmap(self):
        name = simpledialog.askstring('New Mindmap', 'Name:', parent=self)
        if not name:
            return
        data = load()
        mid = str(uuid.uuid4())[:8]
        data['mindmaps'].append({'id': mid, 'name': name, 'nodes': [], 'edges': []})
        data['current_mindmap'] = mid
        save(data)
        self.mindmap_current = mid
        self._refresh_mindmaps()

    def _remove_mindmap(self):
        if not self.mindmap_current:
            return
        if not messagebox.askyesno('Remove', 'Delete this mindmap?'):
            return
        data = load()
        data['mindmaps'] = [m for m in data['mindmaps'] if m['id'] != self.mindmap_current]
        self.mindmap_current = None
        if data['mindmaps']:
            self.mindmap_current = data['mindmaps'][0]['id']
        save(data)
        self._refresh_mindmaps()

    def _on_mindmap_selected(self, event=None):
        name = self.mindmap_var.get()
        data = load()
        for m in data['mindmaps']:
            if m['name'] == name:
                self.mindmap_current = m['id']
                break
        self._draw()

    def _get_current_mindmap(self):
        if not self.mindmap_current:
            return None
        data = load()
        for m in data['mindmaps']:
            if m['id'] == self.mindmap_current:
                return m
        return None

    def _space_press(self, event):
        if isinstance(event.widget, (tk.Entry, tk.Text)):
            return
        self.mindmap_pan_mode = True
        self.mindmap_canvas.config(cursor='fleur')

    def _space_release(self, event):
        self.mindmap_pan_mode = False
        self.mindmap_canvas.config(cursor='crosshair')

    def _mousewheel(self, event):
        if event.delta > 0:
            self._zoom(1.1)
        else:
            self._zoom(0.9)

    def _zoom(self, factor):
        canvas_x = self.mindmap_canvas.canvasx(self.mindmap_canvas.winfo_width() / 2)
        canvas_y = self.mindmap_canvas.canvasy(self.mindmap_canvas.winfo_height() / 2)
        self.mindmap_scale *= factor
        self.mindmap_scale = max(0.1, min(4.0, self.mindmap_scale))
        self.mindmap_zoom_label.config(text=f'{int(self.mindmap_scale * 100)}%')
        self._draw()
        new_cx = canvas_x * self.mindmap_scale + self.mindmap_offset_x
        new_cy = canvas_y * self.mindmap_scale + self.mindmap_offset_y
        if self.mindmap_canvas.bbox('all'):
            self.mindmap_canvas.xview('moveto', (new_cx - self.mindmap_canvas.winfo_width() / 2) / max(1, (self.mindmap_canvas.bbox('all')[2] - self.mindmap_canvas.bbox('all')[0])))
            self.mindmap_canvas.yview('moveto', (new_cy - self.mindmap_canvas.winfo_height() / 2) / max(1, (self.mindmap_canvas.bbox('all')[3] - self.mindmap_canvas.bbox('all')[1])))

    def _canvas_click(self, event):
        if self.mindmap_pan_mode:
            self.mindmap_pan_start = (event.x, event.y)
            self.mindmap_canvas.scan_mark(event.x, event.y)
            return
        items = self.mindmap_canvas.find_overlapping(event.x-5, event.y-5, event.x+5, event.y+5)
        for ent in self.mindmap_edges:
            if ent['line_id'] in items:
                return
        on_node = False
        for n in self.mindmap_nodes:
            if n['rect'] in items or n['text'] in items:
                on_node = True
                break
        if not on_node:
            self.mindmap_selected = None
            self.mindmap_selected_edge = None
            self._draw()

    def _canvas_drag(self, event):
        if self.mindmap_pan_mode and self.mindmap_pan_start:
            self.mindmap_canvas.scan_dragto(event.x, event.y, 1)
            self.mindmap_pan_start = (event.x, event.y)

    def _canvas_release(self, event):
        self.mindmap_pan_start = None

    def _fit_view(self):
        mm = self._get_current_mindmap()
        if not mm or not mm.get('nodes'):
            return
        min_x = min(n.get('x', 0) for n in mm['nodes'])
        max_x = max(n.get('x', 0) + 100 for n in mm['nodes'])
        min_y = min(n.get('y', 0) for n in mm['nodes'])
        max_y = max(n.get('y', 0) + 30 for n in mm['nodes'])
        w = self.mindmap_canvas.winfo_width()
        h = self.mindmap_canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        content_w = max_x - min_x + 100
        content_h = max_y - min_y + 100
        scale_x = w / content_w if content_w > 0 else 1
        scale_y = h / content_h if content_h > 0 else 1
        self.mindmap_scale = min(scale_x, scale_y, 2.0)
        self.mindmap_scale = max(0.1, self.mindmap_scale)
        self.mindmap_offset_x = -min_x * self.mindmap_scale + 50
        self.mindmap_offset_y = -min_y * self.mindmap_scale + 50
        self.mindmap_zoom_label.config(text=f'{int(self.mindmap_scale * 100)}%')
        self._draw()

    def _draw(self):
        self.mindmap_canvas.delete('all')
        self.mindmap_nodes.clear()
        self.mindmap_edges.clear()

        mm = self._get_current_mindmap()
        if not mm:
            w = self.mindmap_canvas.winfo_width() or 600
            h = self.mindmap_canvas.winfo_height() or 400
            self.mindmap_canvas.create_text(w // 2, h // 2, text='Select or create a mindmap',
                                             font=('SF Pro Text', 12), fill='#8e8e93')
            return

        branch_colors = ['#007aff', '#ff3b30', '#ff9500', '#34c759', '#af52de', '#ff2d55', '#5ac8fa', '#ffcc00']

        visible_nodes = set()
        def collect_visible(nid):
            visible_nodes.add(nid)
            node = next((n for n in mm.get('nodes', []) if n['id'] == nid), None)
            if node and node.get('collapsed'):
                return
            for e in mm.get('edges', []):
                if e['from'] == nid:
                    collect_visible(e['to'])

        roots = [n for n in mm.get('nodes', []) if n.get('depth', 0) == 0]
        if not roots:
            roots = mm.get('nodes', [])[:1]
        for root in roots:
            collect_visible(root['id'])

        for n in mm.get('nodes', []):
            n['has_children'] = any(e['from'] == n['id'] for e in mm.get('edges', []))

        for idx, edge in enumerate(mm.get('edges', [])):
            if edge['from'] not in visible_nodes or edge['to'] not in visible_nodes:
                continue
            n1 = next((n for n in mm.get('nodes', []) if n['id'] == edge['from']), None)
            n2 = next((n for n in mm.get('nodes', []) if n['id'] == edge['to']), None)
            if n1 and n2:
                color = branch_colors[idx % len(branch_colors)]
                is_rel = edge.get('type') == 'relationship'
                arrow = 'both' if is_rel else 'last'
                arrowshape = (int(16*self.mindmap_scale), int(20*self.mindmap_scale), int(8*self.mindmap_scale))
                x1, y1, x2, y2 = node_edge_points(n1, n2, self.mindmap_scale, self.mindmap_offset_x, self.mindmap_offset_y)
                cx1, cy1 = x1 + (x2 - x1) * 0.5, y1
                cx2, cy2 = x1 + (x2 - x1) * 0.5, y2
                points = []
                for t in range(0, 101, 5):
                    t /= 100.0
                    x = (1-t)**3 * x1 + 3*(1-t)**2*t * cx1 + 3*(1-t)*t**2 * cx2 + t**3 * x2
                    y = (1-t)**3 * y1 + 3*(1-t)**2*t * cy1 + 3*(1-t)*t**2 * cy2 + t**3 * y2
                    points.extend([x, y])
                _line_width = max(1, int(self.mindmap_thickness_var.get()))
                self.mindmap_edges.append({'edge': edge, 'line_id': self.mindmap_canvas.create_line(points, fill=color, width=_line_width, smooth=True, arrow=arrow, arrowshape=arrowshape)})
                line_id = self.mindmap_edges[-1]['line_id']
                self.mindmap_canvas.tag_bind(line_id, '<Button-1>', lambda e, ed=edge: self._select_edge(e, ed))

        for node in mm.get('nodes', []):
            if node['id'] in visible_nodes:
                self._draw_node(node, branch_colors)

        for ent in self.mindmap_edges:
            self.mindmap_canvas.tag_raise(ent['line_id'])

        bbox = self.mindmap_canvas.bbox('all')
        if bbox:
            pad = 40
            self.mindmap_canvas.config(scrollregion=(bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad))
        else:
            self.mindmap_canvas.config(scrollregion=(0, 0, 100, 100))

    def _draw_node(self, node, branch_colors):
        x = node['x'] * self.mindmap_scale + self.mindmap_offset_x
        y = node['y'] * self.mindmap_scale + self.mindmap_offset_y
        nid = node['id']
        text = node.get('text', '')[:25]
        depth = node.get('depth', 0)
        color_idx = node.get('color', 0)
        style = node.get('style', {})
        is_root = depth == 0

        bg = style.get('backgroundColor')
        fg = style.get('textColor', 'white')
        font_size = style.get('fontSize', 10 if is_root else 9)
        font_weight = 'bold' if (is_root or style.get('fontWeight', 0) >= 600) else ''

        if not bg:
            bg = '#1d1d1f' if is_root else branch_colors[color_idx % len(branch_colors)]

        w = max(100, len(text) * 8 + 24) * self.mindmap_scale
        h = (36 if is_root else 30) * self.mindmap_scale
        r = (8 if is_root else 6) * self.mindmap_scale

        points = [x + r, y, x + w - r, y, x + w, y + r, x + w, y + h - r,
                  x + w - r, y + h, x + r, y + h, x, y + h - r, x, y + r, x + r, y]
        outline_width = 2 if self.mindmap_selected == nid else 0
        outline_color = '#ff9500' if self.mindmap_selected == nid else ''
        rid = self.mindmap_canvas.create_polygon(points, fill=bg, outline=outline_color, width=outline_width, smooth=True)

        marker_ids = []
        markers = node.get('markers', [])
        marker_offset = 4 * self.mindmap_scale
        for m in markers[:3]:
            mid = self.mindmap_canvas.create_text(x + w - marker_offset, y + 8 * self.mindmap_scale,
                                                   text=m, font=('SF Pro Text', int(8 * self.mindmap_scale)))
            marker_ids.append(mid)
            marker_offset += 12 * self.mindmap_scale

        tid = self.mindmap_canvas.create_text(x + w // 2, y + h // 2, text=text, fill=fg,
                                               font=(None, int(font_size * self.mindmap_scale), font_weight))

        task = node.get('task', {})
        extra_items = list(marker_ids)
        if task and task.get('status') == 'done':
            extra_items.append(self.mindmap_canvas.create_text(x + 8 * self.mindmap_scale, y + h // 2,
                                                               text='\u2705', font=('SF Pro Text', int(8 * self.mindmap_scale))))
        if node.get('notes'):
            extra_items.append(self.mindmap_canvas.create_text(x + w - 6 * self.mindmap_scale, y + h - 6 * self.mindmap_scale,
                                                               text='\U0001f4dd', font=('SF Pro Text', int(6 * self.mindmap_scale))))

        if node.get('has_children'):
            cbtn = self.mindmap_canvas.create_text(x + w // 2, y + h + 8 * self.mindmap_scale,
                                                     text='\u2212' if not node.get('collapsed') else '+',
                                                     font=('SF Pro Text', int(10 * self.mindmap_scale), 'bold'), fill=bg)
            self.mindmap_canvas.tag_bind(cbtn, '<Button-1>', lambda e, n=node: self._toggle_collapse(n['id']))
        else:
            cbtn = None

        self.mindmap_nodes.append({'id': nid, 'rect': rid, 'text': tid, 'collapse': cbtn, 'extra': extra_items, 'data': node})
        for tag in [rid, tid]:
            self.mindmap_canvas.tag_bind(tag, '<Button-1>', lambda e, n=node: self._click(e, n))
            self.mindmap_canvas.tag_bind(tag, '<Double-Button-1>', lambda e, n=node: self._double_click(e, n))
            self.mindmap_canvas.tag_bind(tag, '<B1-Motion>', lambda e, n=node: self._motion(e, n))
            self.mindmap_canvas.tag_bind(tag, '<ButtonRelease-1>', lambda e, n=node: self._release(e, n))
            self.mindmap_canvas.tag_bind(tag, '<Button-3>', lambda e, n=node: self._context_menu(e, n))

    def _select_edge(self, event, edge):
        self.mindmap_selected_edge = (edge['from'], edge['to'])
        self.mindmap_selected = None
        for ent in self.mindmap_edges:
            if ent['edge'] is edge:
                self.mindmap_canvas.itemconfig(ent['line_id'], fill='#ff2d55', width=max(2, int(self.mindmap_thickness_var.get()) + 2))

    def _delete_selected(self):
        mm = self._get_current_mindmap()
        if not mm:
            return
        if self.mindmap_selected_edge:
            from_id, to_id = self.mindmap_selected_edge
            mm['edges'] = [e for e in mm.get('edges', []) if not (e['from'] == from_id and e['to'] == to_id)]
            data = load()
            for m in data['mindmaps']:
                if m['id'] == mm['id']:
                    m['edges'] = mm['edges']
                    break
            save(data)
            self.mindmap_selected_edge = None
            self._draw()
            return
        if not self.mindmap_selected:
            messagebox.showinfo('Delete', 'Select a node (click on it) or edge (click on the arrow line) first.')
            return
        to_delete = set()
        def collect(nid):
            to_delete.add(nid)
            for e in mm.get('edges', []):
                if e['from'] == nid:
                    collect(e['to'])
        collect(self.mindmap_selected)
        mm['nodes'] = [n for n in mm.get('nodes', []) if n['id'] not in to_delete]
        mm['edges'] = [e for e in mm.get('edges', []) if e['from'] not in to_delete and e['to'] not in to_delete]
        data = load()
        for m in data['mindmaps']:
            if m['id'] == mm['id']:
                m['nodes'] = mm['nodes']
                m['edges'] = mm['edges']
                break
        save(data)
        self.mindmap_selected = None
        self._draw()

    def _right_click(self, event):
        clicked = self.mindmap_canvas.find_overlapping(event.x-5, event.y-5, event.x+5, event.y+5)
        for n in self.mindmap_nodes:
            if n['rect'] in clicked or n['text'] in clicked:
                mm = self._get_current_mindmap()
                if not mm:
                    return
                from_node = n['data']
                offset_x = 140
                offset_y = (from_node.get('child_count', 0) - from_node.get('depth', 0)) * 40
                new_color = from_node.get('color', 0) if from_node.get('depth', 0) > 0 else (len(mm.get('nodes', [])) % 8)
                new_node = {'id': str(uuid.uuid4())[:6], 'text': 'New Topic',
                            'x': from_node['x'] + offset_x, 'y': from_node['y'] + offset_y,
                            'depth': from_node.get('depth', 0) + 1, 'color': new_color}
                from_node['child_count'] = from_node.get('child_count', 0) + 1
                mm.setdefault('nodes', []).append(new_node)
                mm.setdefault('edges', []).append({'from': from_node['id'], 'to': new_node['id']})
                data = load()
                for m in data['mindmaps']:
                    if m['id'] == mm['id']:
                        m['nodes'] = mm['nodes']
                        m['edges'] = mm['edges']
                        break
                save(data)
                self._draw()
                return
        self.mindmap_connecting = None

    def _click(self, event, node):
        if self.mindmap_connecting == 'pending':
            self.mindmap_connecting = None
            self.mindmap_selected_edge = None
            self._create_edge(self.mindmap_selected, node['id'])
            self.mindmap_selected = node['id']
            self._draw()
            return
        self.mindmap_selected_edge = None
        self.mindmap_selected = node['id']
        data_x = (event.x - self.mindmap_offset_x) / self.mindmap_scale
        data_y = (event.y - self.mindmap_offset_y) / self.mindmap_scale
        mm = self._get_current_mindmap()
        self._mindmap_active = mm
        node_in_mm = next((n for n in mm.get('nodes', []) if n['id'] == node['id']), node) if mm else node
        self.mindmap_drag = {'node': node_in_mm, 'mm': mm,
                              'offset_x': data_x - node_in_mm['x'],
                              'offset_y': data_y - node_in_mm['y'], 'moved': False}
        for n in self.mindmap_nodes:
            if n['id'] == node['id']:
                self.mindmap_canvas.itemconfig(n['rect'], outline='#ff9500', width=2)
            else:
                self.mindmap_canvas.itemconfig(n['rect'], outline='', width=0)

    def _double_click(self, event, node):
        self._click(event, node)

    def _motion(self, event, node):
        if hasattr(self, 'mindmap_drag') and self.mindmap_drag:
            self.mindmap_drag['moved'] = True
            drag_node = self.mindmap_drag['node']
            mm = self.mindmap_drag['mm']
            data_x = (event.x - self.mindmap_offset_x) / self.mindmap_scale
            data_y = (event.y - self.mindmap_offset_y) / self.mindmap_scale
            new_x = data_x - self.mindmap_drag['offset_x']
            new_y = data_y - self.mindmap_drag['offset_y']
            dx = (new_x - drag_node['x']) * self.mindmap_scale
            dy = (new_y - drag_node['y']) * self.mindmap_scale
            drag_node['x'] = new_x
            drag_node['y'] = new_y
            moved_ids = {drag_node['id']}
            if mm and len(moved_ids) > 0:
                data_dx = dx / self.mindmap_scale
                data_dy = dy / self.mindmap_scale
                move_children(mm, drag_node['id'], data_dx, data_dy, moved_ids)
            for n in self.mindmap_nodes:
                if n['id'] in moved_ids:
                    self.mindmap_canvas.move(n['rect'], dx, dy)
                    self.mindmap_canvas.move(n['text'], dx, dy)
                    if n.get('collapse'):
                        self.mindmap_canvas.move(n['collapse'], dx, dy)
                    for mid in n.get('extra', []):
                        self.mindmap_canvas.move(mid, dx, dy)
            self._redraw_edges(moved_ids, mm)

    def _redraw_edges(self, moved_ids, mm):
        if not mm or not self.mindmap_edges:
            return
        branch_colors = ['#007aff', '#ff3b30', '#ff9500', '#34c759', '#af52de', '#ff2d55', '#5ac8fa', '#ffcc00']
        for ent in self.mindmap_edges:
            edge = ent['edge']
            if edge['from'] not in moved_ids and edge['to'] not in moved_ids:
                continue
            n1 = next((n for n in mm.get('nodes', []) if n['id'] == edge['from']), None)
            n2 = next((n for n in mm.get('nodes', []) if n['id'] == edge['to']), None)
            if not n1 or not n2:
                continue
            x1, y1, x2, y2 = node_edge_points(n1, n2, self.mindmap_scale, self.mindmap_offset_x, self.mindmap_offset_y)
            cx1, cy1 = x1 + (x2 - x1) * 0.5, y1
            cx2, cy2 = x1 + (x2 - x1) * 0.5, y2
            points = []
            for t in range(0, 101, 5):
                t /= 100.0
                px = (1-t)**3 * x1 + 3*(1-t)**2*t * cx1 + 3*(1-t)*t**2 * cx2 + t**3 * x2
                py = (1-t)**3 * y1 + 3*(1-t)**2*t * cy1 + 3*(1-t)*t**2 * cy2 + t**3 * y2
                points.extend([px, py])
            color = branch_colors[int(0) % len(branch_colors)]
            is_rel = edge.get('type') == 'relationship'
            arrow = 'both' if is_rel else 'last'
            arrowshape = (int(16*self.mindmap_scale), int(20*self.mindmap_scale), int(8*self.mindmap_scale))
            _line_width = max(1, int(self.mindmap_thickness_var.get()))
            self.mindmap_canvas.coords(ent['line_id'], points)
            self.mindmap_canvas.itemconfig(ent['line_id'], fill=color, width=_line_width, arrow=arrow, arrowshape=arrowshape)

    def _release(self, event, node):
        if hasattr(self, 'mindmap_drag') and self.mindmap_drag:
            if self.mindmap_drag['moved']:
                mm = self.mindmap_drag.get('mm')
                if mm:
                    data = load()
                    for m in data['mindmaps']:
                        if m['id'] == mm['id']:
                            m['nodes'] = mm['nodes']
                            break
                    save(data)
            self.mindmap_drag = None
            self._mindmap_active = None

    def _add_topic(self, event=None):
        mm = self._get_current_mindmap()
        if not mm:
            return
        text = simpledialog.askstring('New Topic', 'Topic text:', parent=self)
        if not text:
            return
        root = None
        for n in mm.get('nodes', []):
            if n.get('depth', 0) == 0:
                root = n
                break
        max_x = max([n.get('x', 0) for n in mm.get('nodes', [])] + [0])
        color = len(mm.get('nodes', [])) % 8
        cw = self.mindmap_canvas.winfo_width() or 600
        ch = self.mindmap_canvas.winfo_height() or 400
        if event:
            x = max(0, event.x - 60)
            y = max(0, event.y - 20)
        elif not root:
            x = (cw / 2 - self.mindmap_offset_x) / self.mindmap_scale - 50
            y = (ch / 2 - self.mindmap_offset_y) / self.mindmap_scale - 15
        else:
            x = max_x + 160
            y = 50 + len(mm.get('nodes', [])) * 50
        node = {'id': str(uuid.uuid4())[:6], 'text': text, 'x': x, 'y': y,
                'depth': 0 if not root else 1, 'color': color}
        mm.setdefault('nodes', []).append(node)
        if root:
            mm.setdefault('edges', []).append({'from': root['id'], 'to': node['id']})
        data = load()
        for m in data['mindmaps']:
            if m['id'] == mm['id']:
                m['nodes'] = mm['nodes']
                m['edges'] = mm['edges']
                break
        save(data)
        self._draw()

    def _add_subtopic_prompt(self):
        if not self.mindmap_selected:
            messagebox.showinfo('Add Subtopic', 'Select a node first (click on it).')
            return
        self._add_subtopic_to(self.mindmap_selected)

    def _add_subtopic_to(self, parent_id):
        mm = self._get_current_mindmap()
        if not mm:
            return
        text = simpledialog.askstring('New Subtopic', 'Text:', parent=self)
        if not text:
            return
        parent = next((n for n in mm.get('nodes', []) if n['id'] == parent_id), None)
        if not parent:
            return
        offset_y = parent.get('child_count', 0) * 50
        color = parent.get('color', 0) if parent.get('depth', 0) > 0 else (len(mm.get('nodes', [])) % 8)
        node = {'id': str(uuid.uuid4())[:6], 'text': text, 'x': parent['x'] + 160,
                'y': parent['y'] + offset_y, 'depth': parent.get('depth', 0) + 1, 'color': color}
        parent['child_count'] = parent.get('child_count', 0) + 1
        mm.setdefault('nodes', []).append(node)
        mm.setdefault('edges', []).append({'from': parent['id'], 'to': node['id']})
        data = load()
        for m in data['mindmaps']:
            if m['id'] == mm['id']:
                m['nodes'] = mm['nodes']
                m['edges'] = mm['edges']
                break
        save(data)
        self._draw()

    def _add_relationship(self):
        if not self.mindmap_selected:
            messagebox.showinfo('Relationship', 'Select a source node first, then click target.')
            self.mindmap_connecting = 'pending'
            return
        if self.mindmap_connecting == 'pending':
            return
        self.mindmap_connecting = 'pending'
        messagebox.showinfo('Relationship', 'Now click the target node for the relationship.')

    def _create_edge(self, from_id, to_id):
        mm = self._get_current_mindmap()
        if not mm:
            return
        if from_id == to_id:
            return
        for e in mm.get('edges', []):
            if e['from'] == from_id and e['to'] == to_id:
                return
        mm.setdefault('edges', []).append({'from': from_id, 'to': to_id, 'type': 'relationship'})
        data = load()
        for m in data['mindmaps']:
            if m['id'] == mm['id']:
                m['edges'] = mm['edges']
                break
        save(data)

    def _toggle_collapse(self, nid):
        mm = self._get_current_mindmap()
        if not mm:
            return
        for n in mm.get('nodes', []):
            if n['id'] == nid:
                n['collapsed'] = not n.get('collapsed', False)
                break
        data = load()
        for m in data['mindmaps']:
            if m['id'] == mm['id']:
                m['nodes'] = mm['nodes']
                break
        save(data)
        self._draw()

    def _context_menu(self, event, node):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='Edit', command=lambda: self._edit(node['id']))
        menu.add_command(label='Add Subtopic', command=lambda: self._add_subtopic_to(node['id']))
        menu.add_command(label='Add Sibling', command=lambda: self._add_sibling_to(node['id']))
        menu.add_separator()
        menu.add_command(label='Delete', command=lambda: self._delete_node(node['id']))
        menu.add_separator()
        menu.add_command(label='Add Marker \u2b50', command=lambda: self._add_marker(node['id'], '\u2b50'))
        menu.add_command(label='Add Marker \u2757', command=lambda: self._add_marker(node['id'], '\u2757'))
        menu.add_command(label='Add Marker \u2705', command=lambda: self._add_marker(node['id'], '\u2705'))
        menu.add_command(label='Clear Markers', command=lambda: self._clear_markers(node['id']))
        menu.post(event.x_root, event.y_root)

    def _edit(self, nid):
        mm = self._get_current_mindmap()
        if not mm:
            return
        node = next((n for n in mm.get('nodes', []) if n['id'] == nid), None)
        if not node:
            return
        x, y = node['x'], node['y']
        w = max(100, len(node.get('text', '')) * 8 + 24)
        h = 36 if node.get('depth', 0) == 0 else 30
        entry = tk.Entry(self.mindmap_canvas, font=('SF Pro Text', 10), bg='white', relief='solid', borderwidth=1)
        entry.insert(0, node.get('text', ''))
        entry_window = self.mindmap_canvas.create_window(x + w // 2, y + h // 2, window=entry, width=w - 10, height=h - 6)
        entry.focus_set()
        entry.select_range(0, 'end')

        def save_edit(event=None):
            new_text = entry.get().strip()
            if new_text:
                mm = self._get_current_mindmap()
                if mm:
                    for n in mm.get('nodes', []):
                        if n['id'] == nid:
                            n['text'] = new_text
                            break
                    data = load()
                    for m in data['mindmaps']:
                        if m['id'] == mm['id']:
                            m['nodes'] = mm['nodes']
                            break
                    save(data)
            self.mindmap_canvas.delete(entry_window)
            self._draw()

        entry.bind('<Return>', save_edit)
        entry.bind('<FocusOut>', save_edit)
        entry.bind('<Escape>', lambda e: (self.mindmap_canvas.delete(entry_window), self._draw()))

    def _add_sibling_to(self, node_id):
        mm = self._get_current_mindmap()
        if not mm:
            return
        parent_id = None
        for e in mm.get('edges', []):
            if e['to'] == node_id:
                parent_id = e['from']
                break
        if parent_id:
            self._add_subtopic_to(parent_id)
        else:
            self._add_topic()

    def _delete_node(self, nid):
        mm = self._get_current_mindmap()
        if not mm:
            return
        if not messagebox.askyesno('Delete', 'Delete this node and all children?'):
            return
        to_delete = set()
        def collect(nid):
            to_delete.add(nid)
            for e in mm.get('edges', []):
                if e['from'] == nid:
                    collect(e['to'])
        collect(nid)
        mm['nodes'] = [n for n in mm.get('nodes', []) if n['id'] not in to_delete]
        mm['edges'] = [e for e in mm.get('edges', []) if e['from'] not in to_delete and e['to'] not in to_delete]
        data = load()
        for m in data['mindmaps']:
            if m['id'] == mm['id']:
                m['nodes'] = mm['nodes']
                m['edges'] = mm['edges']
                break
        save(data)
        self.mindmap_selected = None
        self._draw()

    def _add_marker(self, nid, marker):
        mm = self._get_current_mindmap()
        if not mm:
            return
        for n in mm.get('nodes', []):
            if n['id'] == nid:
                if 'markers' not in n:
                    n['markers'] = []
                if marker not in n['markers']:
                    n['markers'].append(marker)
                break
        data = load()
        for m in data['mindmaps']:
            if m['id'] == mm['id']:
                m['nodes'] = mm['nodes']
                break
        save(data)
        self._draw()

    def _clear_markers(self, nid):
        mm = self._get_current_mindmap()
        if not mm:
            return
        for n in mm.get('nodes', []):
            if n['id'] == nid:
                n['markers'] = []
                break
        data = load()
        for m in data['mindmaps']:
            if m['id'] == mm['id']:
                m['nodes'] = mm['nodes']
                break
        save(data)
        self._draw()
