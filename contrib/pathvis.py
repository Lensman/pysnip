import sys
sys.path.append('..')

import csv
from itertools import izip, chain, starmap, tee
from math import sin, cos, pi
from time import time

from pyglet.gl import *
from pyglet.window import *

from pyspades.vxl import VXLData
from pyspades.common import Vertex3
from pyspades.navigation import Navigation

MAP_X = 512
MAP_Y = 512
MAP_Z = 64

MAX_VERTICES = 150000

class Camera():
    transform = None
    position = None
    right = None
    up = None
    forward = None
    
    def __init__(self, x = 0.0, y = 0.0, z = 0.0):
        self.right = i = Vertex3(1.0, 0.0, 0.0)
        self.up = j = Vertex3(0.0, 1.0, 0.0)
        self.forward = k = Vertex3(0.0, 0.0, -1.0)
        self.position = Vertex3(x, y, z)
        self.transform = (GLfloat * 16)(*[
            i.x, i.y, i.z, 0.0,
            j.x, j.y, j.z, 0.0,
            k.x, k.y, k.z, 0.0,
            x,   y,   z,   1.0])
    
    def apply_view(self):
        glMatrixMode(gl.GL_MODELVIEW)
	glLoadIdentity()
        t = self.transform
        view_matrix = (
            t[0], t[4], t[8],  0.0,
            t[1], t[5], t[9],  0.0,
            t[2], t[6], t[10], 0.0,
            -(t[0] * t[12] + t[1] * t[13] + t[2]  * t[14]),
            -(t[4] * t[12] + t[5] * t[13] + t[6]  * t[14]),
            -(t[8] * t[12] + t[9] * t[13] + t[10] * t[14]),
            1.0)
        glLoadMatrixf((GLfloat * 16)(*view_matrix))
    
    def move_local(self, x, y, z, distance):
        t = self.transform
        dx = (x * t[0] + y * t[4] + z * t[8]) * distance
	dy = (x * t[1] + y * t[5] + z * t[9]) * distance
	dz = (x * t[2] + y * t[6] + z * t[10]) * distance
	t[12] += dx
	t[13] += dy
	t[14] += dz
        self.position.translate(dx, dy, dz)
        
    def move_global(self, x, y, z, distance):
        t = self.transform
        dx = x * distance
        dy = y * distance
        dz = z * distance
	t[12] += dx
	t[13] += dy
	t[14] += dz
        self.position.translate(dx, dy, dz)
    
    def rotate_local(self, x, y, z, deg):
        glMatrixMode(gl.GL_MODELVIEW)
	glPushMatrix()
	glLoadMatrixf(self.transform)
	glRotatef(deg, x, y, z)
	glGetFloatv(GL_MODELVIEW_MATRIX, self.transform)
	glPopMatrix()
    
    def rotate_global(self, x, y, z, deg):
        t = self.transform
	dx = x * t[0] + y * t[1] + z * t[2]
	dy = x * t[4] + y * t[5] + z * t[6]
	dz = x * t[8] + y * t[9] + z * t[10]
        glMatrixMode(gl.GL_MODELVIEW)
	glPushMatrix()
	glLoadMatrixf(t)
	glRotatef(deg, dx, dy, dz)
	glGetFloatv(GL_MODELVIEW_MATRIX, t)
	glPopMatrix()
    
class App(pyglet.window.Window):
    vertex_list = None
    vertex_count = 0
    path_vertex_list = None
    keys = None
    camera = None
    navigation = None
    dx = 0.0
    dy = 0.0
    
    def __init__(self):
        super(App, self).__init__(resizable = True)
        self.camera = Camera(0.0, 5.0, 0.0)
        self.keys = key.KeyStateHandler()
        self.push_handlers(self.keys)
        self.set_exclusive_mouse()
        pyglet.clock.schedule(self.update)
    
    def on_resize(self, width, height):
        height = height or 1
        glViewport(0, 0, width, height)
        glMatrixMode(gl.GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60.0, float(width) / float(height), 0.1, 1000.0)
        glMatrixMode(gl.GL_MODELVIEW)
    
    def on_draw(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glEnable(GL_BLEND)
        glEnable(GL_LINE_SMOOTH)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.camera.apply_view()
        if self.vertex_list:
            glColor4f(1.0, 1.0, 1.0, 0.4)
            glLineWidth(0.5)
            self.vertex_list.draw(pyglet.gl.GL_LINES)
        if self.path_vertex_list:
            glColor3f(1.0, 0.0, 0.0)
            glLineWidth(2.0)
            self.path_vertex_list.draw(pyglet.gl.GL_LINE_STRIP)
    
    def on_key_press(self, symbol, modifiers):
        if symbol == key.ESCAPE:
            pyglet.app.exit()
        elif symbol == key.HOME:
            x, y, z = self.camera.position.get()
            self.path_start = (x, z, -y)
            print 'Set path start to ' + str(self.path_start)
            self.find_path()
        elif symbol == key.END:
            x, y, z = self.camera.position.get()
            self.path_goal = (x, z, -y)
            print 'Set path goal to ' + str(self.path_goal)
            self.find_path()
    
    def on_mouse_motion(self, x, y, dx, dy):
        self.dx += dx
        self.dy += dy
    
    def update(self, dt):
        keys = self.keys
        camera = self.camera
        sensitivity = 0.1
        if self.dx != 0.0:
            camera.rotate_global(0.0, -1.0, 0.0, self.dx * sensitivity)
        if self.dy != 0.0:
            camera.rotate_local(1.0, 0.0, 0.0, self.dy * sensitivity)
        self.dx = self.dy = 0.0
        speed = 150.0 if keys[key.LSHIFT] or keys[key.RSHIFT] else 50.0
        if keys[key.W]:
            camera.move_local(0.0, 0.0, -1.0, speed * dt)
        elif keys[key.S]:
            camera.move_local(0.0, 0.0, 1.0, speed * dt)
        if keys[key.A]:
            camera.move_local(-1.0, 0.0, 0.0, speed * dt)
        elif keys[key.D]:
            camera.move_local(1.0, 0.0, 0.0, speed * dt)
        if keys[key.SPACE]:
            camera.move_global(0.0, 1.0, 0.0, speed * dt)
        elif keys[key.LCTRL] or keys[key.RCTRL]:
            camera.move_global(0.0, -1.0, 0.0, speed * dt)
    
    def load_csv(self, path):
        vertex_indices = []
        vertex_data = []
        pos_to_index = {}
        links = {}
        lines = 0
        
        def get_vertex_index(x, y, z):
            x, y, z = int(x), int(y), int(z)
            pos = x + y * MAP_Y + z * MAP_X * MAP_Y
            if pos in pos_to_index:
                return pos_to_index[pos]
            i = self.vertex_count
            self.vertex_count += 1
            pos_to_index[pos] = i
            links[i] = set()
            vertex_data.extend((x, -z, y))
            return i
        
        with open(path, 'rb') as file:
            reader = csv.reader(file)
            for row in reader:
                pos, x, y, z, height = row[:5]
                i = get_vertex_index(x, y, z)
                next_vertex_iter = izip(*[iter(row[5:])] * 3)
                for x, y, z in next_vertex_iter:
                    next_i = get_vertex_index(x, y, z)
                    if next_i in links[i] or i in links[next_i]:
                        continue
                    links[i].add(next_i)
                    links[next_i].add(i)
                    lines += 1
                    vertex_indices.extend((i, next_i))
                if self.vertex_count > MAX_VERTICES:
                    break
        
        self.vertex_list = pyglet.graphics.vertex_list_indexed(self.vertex_count,
            vertex_indices, ('v3i/static', tuple(vertex_data)))
    
    def load_map(self, name):
        try:
            data = VXLData(open('../feature_server/maps/%s.vxl' % name, 'rb'))
        except (IOError):
            print "Couldn't open map '%s'" % name
            return False
        current_time = time()
        self.navigation = Navigation(data)
        dt = time() - current_time
        print 'Navgraph contains %s nodes. Generation took %s' % (
            self.navigation.get_node_count(), dt)
        return True
    
    def find_path(self):
        if not self.navigation:
            return
        x1, y1, z1 = self.path_start
        x2, y2, z2 = self.path_goal
        current_time = time()
        for i in xrange(100):
            path = self.navigation.find_path(x1, y1, z1, x2, y2, z2)
        dt = time() - current_time
        print 'Solution has %s nodes, took %s' % (len(path), dt)
        if path:
            def map_vert(x, y, z):
                return x, -z, y
            vertex_count = len(path)
            vertex_data = tuple(chain(*starmap(map_vert, path)))
            color_data = (255, 0, 0) * vertex_count
            self.path_vertex_list = pyglet.graphics.vertex_list(vertex_count,
                ('v3i/static', vertex_data), ('c3B/static', color_data))

def main():
    window = App()
    if window.load_map('cord'):
        #~ window.navigation.print_navgraph_csv()
        #~ window.path_start = (128, 256, 2)
        window.path_start = (73, 226, 42)
        #~ window.path_goal = (512-128, 256, 2)
        window.path_goal = (356, 223, 32)
        window.find_path()
        #~ window.find_path()
        #~ window.find_path()
        #~ window.find_path()
    window.load_csv('./navgraph.csv')
    pyglet.app.run()

if __name__ == '__main__':
    main()