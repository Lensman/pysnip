from twisted.internet.task import LoopingCall
from pyspades.bytes import ByteReader
from pyspades.packet import load_client_packet
from pyspades.server import block_action
from pyspades.collision import collision_3d
from pyspades.constants import *
from pyspades import contained as loaders
from commands import add, admin, get_player

SCULPT_RAY_LENGTH = 128.0
SCULPT_INTERVAL = 0.02

try:
    from preservecolor import destroy_block
except ImportError:
    def destroy_block(protocol, x, y, z):
        if protocol.map.get_solid(x, y, z) is None:
            return False
        block_action.value = DESTROY_BLOCK
        block_action.player_id = 32
        block_action.x = x
        block_action.y = y
        block_action.z = z
        protocol.send_contained(block_action, save = True)
        return True

class HandyLoopingCall(LoopingCall):
    def set_running(self, run, interval):
        if not self.running and run:
            self.start(interval, now = True)
        elif self.running and not run:
            self.stop()


def sculpt(connection, player = None):
    protocol = connection.protocol
    if player is not None:
        player = get_player(protocol, player)
    elif connection in protocol.players:
        player = connection
    else:
        raise ValueError()
    
    player.sculpting = sculpting = not player.sculpting
    if sculpting:
        player.sculpt_loop = HandyLoopingCall(sculpt_ray, player)
    else:
        if player.sculpt_loop and player.sculpt_loop.running:
            player.sculpt_loop.stop()
        player.sculpt_loop = None
    
    message = 'now sculpting' if sculpting else 'no longer sculpting'
    player.send_chat("You're %s" % message)
    if connection is not player and connection in protocol.players:
        connection.send_chat('%s is %s' % (player.name, message))
    protocol.irc_say('* %s is %s' % (player.name, message))

add(sculpt)

def build_block(protocol, player, x, y, z):
    protocol.map.set_point(x, y, z, player.color)
    block_action.x = x
    block_action.y = y
    block_action.z = z
    block_action.player_id = player.player_id
    block_action.value = BUILD_BLOCK
    protocol.send_contained(block_action, save = True)
    return True

def axes(x, y, z):
    yield x, y, z
    yield x - 1, y, z
    yield x + 1, y, z
    yield x, y - 1, z
    yield x, y + 1, z
    yield x, y, z - 1
    yield x, y, z + 1

def sculpt_ray(player):
    if player.tool != SPADE_TOOL:
        return


    location = player.world_object.cast_ray(SCULPT_RAY_LENGTH)
    if location:
        px, py, pz = player.get_location()
        x, y, z = location
        map = player.protocol.map
                    
        #if not player.sculpt_primary and  player.sculpt_secondary:

        if collision_3d(px, py, pz, x, y, z, MAX_DIG_DISTANCE / 2):
            # sculpting too close
            print "CLOSE"
            return

        if player.on_block_destroy(x, y, z, DESTROY_BLOCK) == False:
            return
        if z > 62 or not destroy_block(player.protocol, x, y, z):
            return
        if map.get_solid(x, y, z):
            # sculpt allows destroying base blocks, but the API doesn't
            # like this. work around it and force destruction
            map.remove_point(x, y, z)
            map.check_node(x, y, z, True)
        player.on_block_removed(x, y, z)

def apply_script(protocol, connection, config):
    class SculptConnection(connection):
        sculpting = False
        sculpt_primary = False
        sculpt_secondary = False
        sculpt_loop = None
        
        def on_kill(self, killer, type, grenade):
            self.sculpt_primary = self.sculpt_secondary = False
            if self.sculpt_loop and self.sculpt_loop.running:
                self.sculpt_loop.stop()
            return connection.on_kill(self, killer, type, grenade)
        
        def on_reset(self):
            self.sculpt_primary = self.sculpt_secondary = False
            if self.sculpt_loop and self.sculpt_loop.running:
                self.sculpt_loop.stop()
            connection.on_reset(self)
        
        def on_disconnect(self):
            if self.sculpt_loop and self.sculpt_loop.running:
                self.sculpt_loop.stop()
            self.sculpt_loop = None
            connection.on_disconnect(self)
        
        def on_primary_fire_set(self, primary):
            if self.sculpting and self.sculpt_loop and self.tool == SPADE_TOOL:
                self.sculpt_primary = primary
                run = primary or self.world_object.secondary_fire
                self.sculpt_loop.set_running(run, SCULPT_INTERVAL)
            #~ connection.on_primary_fire_set(self, primary)
        
        def on_secondary_fire_set(self, secondary):
            if self.sculpting and self.sculpt_loop and self.tool == SPADE_TOOL:
                self.sculpt_secondary = secondary
                run = secondary or self.world_object.primary_fire
                self.sculpt_loop.set_running(run, SCULPT_INTERVAL)
            connection.on_secondary_fire_set(self, secondary)
        
        def loader_received(self, loader):
            # work around the on_shoot_set event only firing with weapon or spade
            # on_primary_fire_set should be added in server.py, some day
            if self.sculpting:
                if self.player_id is not None:
                    contained = load_client_packet(ByteReader(loader.data))
                    if self.hp:
                        if contained.id == loaders.WeaponInput.id:
                            primary = contained.primary
                            if self.world_object.primary_fire != primary:
                                self.on_primary_fire_set(primary)
            return connection.loader_received(self, loader)
        
        def refill(self, local = False):
            # prevent refill spamming, only do it if necessary
            if not local and self.sculpting and self.god:
                if self.hp == 100 and self.grenades == 3 and self.blocks == 50:
                    return
            connection.refill(self, local)
    
    return protocol, SculptConnection
