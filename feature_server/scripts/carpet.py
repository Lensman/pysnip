from collections import deque
from math import cos
from twisted.internet.task import LoopingCall
from pyspades.server import input_data, block_action, set_color
from pyspades.common import Vertex3, make_color
from pyspades.constants import *
from commands import add, admin, get_player

CARPET_COLOR = (0, 0, 0)
CARPET_INTERVAL = 0.2

@admin
def carpet(connection, player = None):
    protocol = connection.protocol
    if player is not None:
        player = get_player(protocol, player)
    elif connection in protocol.players:
        player = connection
    else:
        raise ValueError()
    
    player.carpet = not player.carpet
    if player.carpet:
        player.carpet_blocks = deque()
        if player.carpet_loop is None:
            player.carpet_loop = LoopingCall(carpet_cycle, protocol, player)
        player.carpet_loop.start(CARPET_INTERVAL)
    else:
        while player.carpet_blocks:
            destroy_block(protocol, *player.carpet_blocks.pop())
        player.carpet_loop.stop()
    
    message = 'now carpetwalking' if player.carpet else 'no longer carpetwalking'
    player.send_chat("You're %s" % message)
    if connection is not player and connection in protocol.players:
        connection.send_chat('%s is %s' % (player.name, message))
    protocol.irc_say('* %s is %s' % (player.name, message))

add(carpet)

sgn = lambda x: (x > 0) - (x < 0)

def set_block_color(protocol, color):
    set_color.value = color
    set_color.player_id = 32
    protocol.send_contained(set_color, save = True)

def destroy_block(protocol, x, y, z):
    if protocol.map.destroy_point(x, y, z):
        block_action.value = DESTROY_BLOCK
        block_action.player_id = 32
        block_action.x = x
        block_action.y = y
        block_action.z = z
        protocol.send_contained(block_action, save = True)
        return True
    return False

def build_block(protocol, player, x, y, z, color):
    if protocol.map.build_point(x, y, z, color):
        block_action.value = BUILD_BLOCK
        block_action.player_id = player.player_id
        block_action.x = x
        block_action.y = y
        block_action.z = z
        protocol.send_contained(block_action, save = True)
        return True
    return False

def is_placing_safe(map, u, v, w, x, y, z):
    if x < 0 or y < 0 or z < 0 or x >= 512 or y >= 512 or z >= 62:
        return True
    if not map.get_solid(x, y, z):
        return True
    if not map.is_surface(x, y, z):
        return True

def add_carpet_block(protocol, player, x, y, z):
    x, y, z = int(x), int(y), int(z)
    y = y - ((x + y) % 2)
    z = z / 2 * 2
    if ((x < 1 or protocol.map.is_surface(x - 1, y, z)) and
        (y < 1 or protocol.map.is_surface(x, y - 1, z)) and
        (z < 1 or protocol.map.is_surface(x, y, z - 1)) and
        (x >= 511 or protocol.map.is_surface(x + 1, y, z)) and
        (y >= 511 or protocol.map.is_surface(x, y + 1, z)) and
        (z >= 511 or protocol.map.is_surface(x, y, z + 1)) and
        build_block(protocol, player, x, y, z, CARPET_COLOR)):
        player.carpet_blocks.append((x, y, z))
    while len(player.carpet_blocks) > 5:
        destroy_block(protocol, *player.carpet_blocks.popleft())
    return x, y, z

def carpet_cycle(protocol, player):
    obj = player.world_object
    if obj.dead or obj.up == obj.down == obj.left == obj.right == False:
        return
    pos = obj.position
    x, y = obj.orientation.x, obj.orientation.y
    if obj.right or obj.left:
        x, y = -y, x
    if obj.down or obj.left:
        x, y = -x, -y
    v = Vertex3(x, y, obj.orientation.z)
    v.normalize()
    #~ v *= cos(abs(obj.orientation.z))
    to_add = [
        (pos.x,            pos.y,            pos.z + 3.0),
        (pos.x + sgn(v.x), pos.y + sgn(v.y), pos.z + 3.0),
        (pos.x + v.x,      pos.y + v.y,      pos.z + 3.0),
        (pos.x + v.x * 2,  pos.y + v.y * 2,  pos.z + 3.0)]
    for x, y, z in to_add:
        add_carpet_block(protocol, player, x, y, z)

def apply_script(protocol, connection, config):
    class CarpetConnection(connection):
        carpet = False
        carpet_blocks = None
        carpet_loop = None
        
        def on_disconnect(self):
            if self.carpet_loop and self.carpet_loop.running:
                self.carpet_loop.stop()
            self.carpet_loop = None
            connection.on_disconnect(self)
        
        def on_map_change(self, map):
            self.carpet = False
            self.carpet_blocks = None
            connection.on_map_change(self, map)
        
        def on_walk_update(self, up, down, left, right):
            if self.carpet:
                carpet_cycle(self.protocol, self)
            return connection.on_walk_update(self, up, down, left, right)
        
        def on_animation_update(self, fire, jump, crouch, aim):
            if self.carpet and jump:
                x, y, z = self.world_object.position.get()
                x, y, z = add_carpet_block(self.protocol, self, x, y, z + 2.0)
                self.set_location((x, y, z - 2.0))
            return connection.on_animation_update(self, fire, jump, crouch, aim)
    
    return protocol, CarpetConnection