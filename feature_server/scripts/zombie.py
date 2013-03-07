## ORIGINAL SCRIPT BY DANY0

## fix v1.1
## CHANGES:
## grabbing intel no longer heals or does damage for either team
## "You're a zombie you don't know how to use a gun! Take the spade!" message will display if zombie shoots,
##    instead of on_position_update to (hopefully) reduce warping and some lag.
## Added a message explaining intel capturing zombie using guns in on_capture

## FIXES:
## on_hit no longer calls hit()/return false. Instead passes hit_amount along, (togglekill/aimbot2 fix)
## /build is no longer exploitable by alternating /b 0 and /b # to build for free
## on_destroy will no longer ignore togglebuild
## on_spawn uses set_location_safe now

from pyspades.server import orientation_data, grenade_packet, weapon_reload
from pyspades.common import coordinates, Vertex3
from pyspades.world import Grenade
from commands import add, admin
from math import sin, floor, atan2
from pyspades.constants import *
from pyspades.server import block_action
from pyspades.collision import distance_3d
from twisted.internet.task import LoopingCall
import random

MESSAGE_UPDATE_RATE = 3

HEAL_RATE = 1000

ZOMBIE = 5
HUMAN = 10

QUICKBUILD_WALL = ((0, 0, 0), (-1, 0, 0), (-1, 0, 1), (-2, 0, 0), (-2, 0, 1), 
                   (-3, 0, 0), (-3, 0, 1), (0, 0, 1), (1, 0, 0), (1, 0, 1), 
                   (2, 0, 0), (2, 0, 1), (3, 0, 0), (3, 0, 1), (-3, -1, 0), (-3, -1, 1), (-3, -2, 0),
                   (-3, -2, 1),(3, -1, 0), (3, -1, 1), (3, -2, 0), (3, -2, 1))
QUICKBUILD_BUNKER = ((0, 0, 0), (-1, 0, 0), (-1, 0, 1), (-1, 0, 2), 
                     (0, 0, 2), (1, 0, 0), (1, 0, 1), (1, 0, 2), 
                     (2, 0, 0), (2, 0, 2), (-2, 0, 2), (-2, 0, 0), 
                     (3, 0, 0), (3, 0, 1), (3, 0, 2), (-3, 0, 0), 
                     (-3, 0, 1), (-3, 0, 2), (3, 0, 3), (2, 0, 3), 
                     (1, 0, 3), (0, 0, 3), (-1, 0, 3), (-2, 0, 3), 
                     (-3, 0, 3), (-3, -1, 0), (-3, -1, 1), (-3, -1, 2), 
                     (-3, -1, 3), (-3, -2, 3), (-3, -2, 2), (-3, -2, 1), 
                     (-3, -2, 0), (-3, -3, 0), (-3, -3, 1), (-3, -3, 2), 
                     (-3, -3, 3), (-2, -1, 3), (-2, -2, 3), (-2, -3, 3), 
                     (-1, -1, 3), (-1, -2, 3), (-1, -3, 3), (0, -1, 3), 
                     (0, -2, 3), (0, -3, 3), (1, -1, 3), (1, -2, 3), 
                     (1, -3, 3), (2, -1, 3), (2, -2, 3), (2, -3, 3), 
                     (3, -3, 3), (3, -3, 0), (3, -3, 1), (3, -3, 2), 
                     (3, -2, 3), (3, -2, 0), (3, -2, 1), (3, -2, 2), 
                     (3, -1, 0), (3, -1, 1), (3, -1, 2), (3, -1, 3), (0, 1, 0), (2, 1, 0), (-2, 1, 0),
                     (1, -1, 0), (1, -1, 1), (1, -1, 2), (-1, -1, 0), (-1, -1, 1), (-1, -1, 2),
                     (2, -3, 0), (2, -3, 1), (2, -3, 2), (-2, -3, 0), (-2, -3, 1), (-2, -3, 2))
QUICKBUILD_TENT = ((0,0,1), (0,0,2), (1,0,0), (1,0,1), (-1,0,0), (-1,0,1), (2,0,0), (-2,0,0), (0,1,0),
                   (0,1,1),(0,-1,0),(0,-1,1), (0,2,0), (0,-2,0))
QUICKBUILD_MOBILEFORT = ((-2, 0, 0), (-1, 0, 0), (1, 0, 0), (2, 0, 0),
             (-2, -4, 0), (-1, -4, 0), (1, -4, 0), (2, -4, 0),
             (-2, -1, 0), (2, -1, 0), (-2, -2, 0), (2, -2, 0), (-2, -3, 0), (2, -3, 0),
             (-2, 0, 1), (0, 0, 1), (2, 0, 1),
             (-2, -4, 1), (-1, -4, 1), (1, -4, 1), (2, -4, 1),
             (-2, -2, 1), (2, -2, 1),
             (-2, 0, 2), (-1, 0, 2), (0, 0, 2), (1, 0, 2), (2, 0, 2),
             (-2, -4, 2), (-1, -4, 2), (0, -4, 2), (1, -4, 2), (2, -4, 2),
             (-2, -1, 2), (2, -1, 2), (-2, -2, 2), (2, -2, 2), (-2, -3, 2), (2, -3, 2),
             (-2,  0, 3), (-1,  0, 3), (0,  0, 3), (1,  0, 3), (2,  0, 3),
             (-2, -1, 3), (-1, -1, 3), (0, -1, 3), (1, -1, 3), (2, -1, 3),
             (-2, -2, 3), (-1, -2, 3), (0, -2, 3), (1, -2, 3), (2, -2, 3),
             (-2, -3, 3), (-1, -3, 3), (0, -3, 3), (1, -3, 3), (2, -3, 3),
             (-2, -4, 3), (-1, -4, 3), (0, -4, 3), (1, -4, 3), (2, -4, 3))
QUICKBUILD_BIGWALL = ((0, 0, 0),(-1, 0, 0),(-1, 0, 1),(-2, 0, 0),(-2, 0, 1),(-3, 0, 0),(-3, 0, 1),(0, 0, 1),
                      (1, 0, 0),(1, 0, 1), (2, 0, 0),(2, 0, 1),(3, 0, 0),(3, 0, 1),(-3, -1, 0),(-3, -1, 1),
                      (-3, -2, 0),(-3, -2, 1),(3, -1, 0),(3, -1, 1),(3, -2, 0),(3, -2, 1),(0, 0, 2),(-1, 0, 2),
                      (-2, 0, 2),(-3, 0, 2),(1, 0, 2),(2, 0, 2),(3, 0, 2),(-3, -1, 2),(-3, -2, 2),(3, -1, 2),
                      (3, -2, 2),(0, -1, 0),(-1, -1, 0),(-2, -1, 0),(-3, -1, 0),(1, -1, 0),(2, -1, 0),(3, -1, 0),
                      (-3, -3, 1), (3, -3, 1))
QUICKBUILD_DEFENSEWALL =((0, 0, 0), (-1, 0, 0), (-1, 0, 1), (-2, 0, 0), (-2, 0, 1), 
                   (-3, 0, 0), (-3, 0, 1), (0, 0, 1), (1, 0, 0), (1, 0, 1), 
                   (2, 0, 0), (2, 0, 1), (3, 0, 0), (3, 0, 1), (-3, -1, 0), (-3, -1, 1), (-3, -2, 0),
                   (-3, -2, 1),(3, -1, 0), (3, -1, 1), (3, -2, 0), (3, -2, 1),
                         (0, 0, 2), (-1, 0, 2), (-1, 0, 3), (-2, 0, 2), (-2, 0, 3), 
                   (-3, 0, 2), (-3, 0, 3), (0, 0, 3), (1, 0, 2), (1, 0, 3), 
                   (2, 0, 2), (2, 0, 3), (3, 0, 2), (3, 0, 3), (-3, -1, 2), (-3, -1, 3), (-3, -2, 2),
                   (-3, -2, 3),(3, -1, 2), (3, -1, 3), (3, -2, 2), (3, -2, 3),
                   (0,-1,0),(1,-1,0),(-1,-1,0),(2,-1,0),(-2,-1,0),
                   (0,-1,1),(1,-1,1),(-1,-1,1),(2,-1,1),(-2,-1,1))
QUICKBUILD_FORT = ((0,0,0),(0,0,1),(0,0,2),(1,0,0),(1,0,1),(1,0,2),(-1,0,0),(-1,0,1),(-1,0,2),
                   (2,0,0),(2,0,1),(2,0,2),(-2,0,0),(-2,0,1),(-2,0,2),(3,0,0),(3,0,1),(3,0,2),
                   (-3,0,0),(-3,0,1),(-3,0,2),(4,0,0),(4,0,1),(4,0,2),(-4,0,0),(-4,0,1),(-4,0,2),
                   (0,1,0),(0,1,1),(0,1,2),(1,1,0),(1,1,1),(1,1,2),(-1,1,0),(-1,1,1),(-1,1,2),
                   (2,1,0),(2,1,1),(2,1,2),(-2,1,0),(-2,1,1),(-2,1,2),(3,1,0),(3,1,1),(3,1,2),
                   (-3,1,0),(-3,1,1),(-3,1,2),(4,1,0),(4,1,1),(4,1,2),(-4,1,0),(-4,1,1),(-4,1,2),
                   (0,2,0),(0,2,1),(0,2,2),(1,2,0),(1,2,1),(1,2,2),(-1,2,0),(-1,2,1),(-1,2,2),
                   (2,2,0),(2,2,1),(2,2,2),(-2,2,0),(-2,2,1),(-2,2,2),(3,2,0),(3,2,1),(3,2,2),
                   (-3,2,0),(-3,2,1),(-3,2,2),(4,2,0),(4,2,1),(4,2,2),(-4,2,0),(-4,2,1),(-4,2,2),
                   (0,3,0),(1,3,0),(-1,3,0),(2,3,0),(-2,3,0),(3,3,0),(-3,3,0),(4,3,0),(-4,3,0),
                   (0,2,3),(2,2,3),(4,2,3),(-2,2,3),(-4,2,3))
QUICKBUILD_BRIDGE = ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (-1, 1, 0), 
                     (0, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0), 
                     (-1, 2, 0), (-1, 3, 0), (0, 3, 0), (1, 3, 0), 
                     (1, 4, 0), (0, 4, 0), (-1, 4, 0), (-1, 5, 0), 
                     (0, 5, 0), (1, 5, 0), (1, 6, 0), (0, 6, 0), 
                     (-1, 6, 0), (-1, 7, 0), (0, 7, 0), (1, 7, 0), 
                     (1, 8, 0), (0, 8, 0), (-1, 8, 0), (-1, 9, 0), 
                     (0, 9, 0), (1, 9, 0), (1, 10, 0), (0, 10, 0), 
                     (-1, 10, 0), (-1, 11, 0), (0, 11, 0), (1, 11, 0), 
                     (1, 12, 0), (0, 12, 0), (-1, 12, 0), (-1, 13, 0), 
                     (0, 13, 0), (1, 13, 0), (1, 14, 0), (0, 14, 0), 
                     (-1, 14, 0), (-1, 15, 0), (0, 15, 0), (1, 15, 0), 
                     (1, 16, 0), (0, 16, 0), (-1, 16, 0), (-1, 17, 0), 
                     (0, 17, 0), (1, 17, 0), (1, 18, 0), (0, 18, 0), 
                     (-1, 18, 0), (-1, 19, 0), (0, 19, 0), (1, 19, 0), 
                     (1, 20, 0), (0, 20, 0), (-1, 20, 0), (-1, 21, 0), 
                     (0, 21, 0), (1, 21, 0), (1, 22, 0), (0, 22, 0), 
                     (-1, 22, 0), (-1, 23, 0), (0, 23, 0), (1, 23, 0), 
                     (0, 24, 0), (1, 24, 0), (-1, 24, 0), (-1, 25, 0), 
                     (0, 25, 0), (1, 25, 0),
                     (-1, 1, 1), (0, 1, 1), (1, 1, 1), (1, 2, 1), (0, 2, 1), 
                     (-1, 2, 1), (-1, 3, 1), (0, 3, 1), (1, 3, 1), 
                     (1, 4, 1), (0, 4, 1), (-1, 4, 1), (-1, 5, 1), 
                     (0, 5, 1), (1, 5, 1), (1, 6, 1), (0, 6, 1), 
                     (-1, 6, 1), (-1, 7, 1), (0, 7, 1), (1, 7, 1), 
                     (1, 8, 1), (0, 8, 1), (-1, 8, 1), (-1, 9, 1), 
                     (0, 9, 1), (1, 9, 1), (1, 10, 1), (0, 10, 1), 
                     (-1, 10, 1), (-1, 11, 1), (0, 11, 1), (1, 11, 1), 
                     (1, 12, 1), (0, 12, 1), (-1, 12, 1), (-1, 13, 1), 
                     (0, 13, 1), (1, 13, 1), (1, 14, 1), (0, 14, 1), 
                     (-1, 14, 1), (-1, 15, 1), (0, 15, 1), (1, 15, 1), 
                     (1, 16, 1), (0, 16, 1), (-1, 16, 1), (-1, 17, 1), 
                     (0, 17, 1), (1, 17, 1), (1, 18, 1), (0, 18, 1), 
                     (-1, 18, 1), (-1, 19, 1), (0, 19, 1), (1, 19, 1), 
                     (1, 20, 1), (0, 20, 1), (-1, 20, 1), (-1, 21, 1), 
                     (0, 21, 1), (1, 21, 1), (1, 22, 1), (0, 22, 1), 
                     (-1, 22, 1), (-1, 23, 1), (0, 23, 1), (1, 23, 1), 
                     (0, 24, 1), (1, 24, 1), (-1, 24, 1), (-1, 25, 1), 
                     (0, 25, 1), (1, 25, 1),
                      (1, 2, 2), (0, 2, 2), 
                     (-1, 2, 2), (-1, 3, 2), (0, 3, 2), (1, 3, 2), 
                     (1, 4, 2), (0, 4, 2), (-1, 4, 2), (-1, 5, 2), 
                     (0, 5, 2), (1, 5, 2), (1, 6, 2), (0, 6, 2), 
                     (-1, 6, 2), (-1, 7, 2), (0, 7, 2), (1, 7, 2), 
                     (1, 8, 2), (0, 8, 2), (-1, 8, 2), (-1, 9, 2), 
                     (0, 9, 2), (1, 9, 2), (1, 10, 2), (0, 10, 2), 
                     (-1, 10, 2), (-1, 11, 2), (0, 11, 2), (1, 11, 2), 
                     (1, 12, 2), (0, 12, 2), (-1, 12, 2), (-1, 13, 2), 
                     (0, 13, 2), (1, 13, 2), (1, 14, 2), (0, 14, 2), 
                     (-1, 14, 2), (-1, 15, 2), (0, 15, 2), (1, 15, 2), 
                     (1, 16, 2), (0, 16, 2), (-1, 16, 2), (-1, 17, 2), 
                     (0, 17, 2), (1, 17, 2), (1, 18, 2), (0, 18, 2), 
                     (-1, 18, 2), (-1, 19, 2), (0, 19, 2), (1, 19, 2), 
                     (1, 20, 2), (0, 20, 2), (-1, 20, 2), (-1, 21, 2), 
                     (0, 21, 2), (1, 21, 2), (1, 22, 2), (0, 22, 2), 
                     (-1, 22, 2), (-1, 23, 2), (0, 23, 2), (1, 23, 2), 
                     (0, 24, 2), (1, 24, 2), (-1, 24, 2), (-1, 25, 2), 
                     (0, 25, 2), (1, 25, 2))
QUICKBUILD_STRUCTURES = (QUICKBUILD_WALL, QUICKBUILD_BUNKER, QUICKBUILD_TENT,
                         QUICKBUILD_MOBILEFORT, QUICKBUILD_BIGWALL, QUICKBUILD_DEFENSEWALL,
                         QUICKBUILD_FORT,QUICKBUILD_BRIDGE)
QUICKBUILD_DESCRIPTION = ('wall', 'bunker', 'tent', 'mobilefort','bigwall','defensewall','fort', 'bridge')
# Cost is in number of kills
QUICKBUILD_COST = (0, 1, 0, 1, 2, 3, 4, 5)

# Don't touch these values
EAST = 0
SOUTH = 1
WEST = 2
NORTH = 3
UPDATE_RATE = 1.0

@admin
def zhp(connection, value):
    if value == 0:
        a = True
    protocol = connection.protocol
    protocol.ZOMBIE_HP = abs(float(value))
    connection.send_chat('ZOMBIE_HP is now '+str(abs(int(value))))

@admin
def ztel(connection, value):
    protocol = connection.protocol
    protocol.ZOMBIE_TELEPORT = abs(int(value))
    connection.send_chat('Zombies now teleport '+str(abs(int(value)))+' blocks high')

@admin
def zspawnhigh(connection, value):
    protocol = connection.protocol
    val = abs(int(value))
    if val >= 10:
        protocol.spawnhigh = abs(value)
        protocol.com = True
        connection.send_chat('Zombies will now spawn '+str(val)+' blocks high')
    elif val < 10:
        protocol.spawnhigh = 0
        protocol.com = False
        connection.send_chat('Disabling zombie spawning up in the air')
    return value

def q(connection):
    build(connection, 0)

def g(connection):
    build(connection, 7)
    
def b(connection, structure = None):
    build(connection, structure)
            
def build(connection, structure = None):
    if connection.mode != HUMAN:
        connection.send_chat("You can't build as a zombie.")
        return
    if structure == None:
        connection.send_chat('/b 0   wall (free)             /b 1   bunker (1 kills)')
        connection.send_chat('/b 2   tent (free)             /b 3   mobile fort (1 kill)')
        connection.send_chat('/b 4   big wall (2 kills)      /b 5   defense wall (3 kills)')
        connection.send_chat('/b 6   fort (4 kills)          /b 7   ginormous bridge (5 kills)')
        connection.send_chat('                Type /b # to select; alternative /b 0 is /q; /b7 is /g')
    else:
        invalid_structure = False
        try:
            structure = int(structure)
            if structure >= len(QUICKBUILD_STRUCTURES):
                invalid_structure = True
            else:
                connection.quickbuild = structure
        except ValueError:
            invalid_structure = True
        if invalid_structure:
            connection.send_chat('The structure that you entered is invalid.')
            return
        cost = QUICKBUILD_COST[structure]
        if connection.quickbuild_points >= cost:
            connection.quickbuild_points -= cost
            connection.send_chat('The next block you place will build a ' +
                                 QUICKBUILD_DESCRIPTION[structure]+'.')
            connection.quickbuild_enabled = True
        else:
            connection.send_chat('You need ' + 
                str(cost-connection.quickbuild_points) +
                ' more zombie heads if you want to build this structure.')
            connection.quickbuild_enabled = False

def zombiestat(connection):
    connection.send_chat('Zombies 1.0.0 RC6 by Dany0')
    connection.send_chat('Zombie health is '+str(connection.protocol.ZOMBIE_HP)+', Zombies teleport '+str(connection.protocol.ZOMBIE_TELEPORT)+' blocks high')

add(q)
add(ztel)
add(zhp)
add(b)
add(build)
add(zombiestat)
add(zspawnhigh)
def empty_weapon(player):
    weapon = player.weapon_object
    weapon.set_shoot( SPADE_TOOL )
    weapon.current_ammo = 0
    weapon.current_stock = 0
    weapon_reload.player_id = player.player_id
    weapon_reload.clip_ammo = weapon.current_ammo
    weapon_reload.reserve_ammo = weapon.current_stock
    player.send_contained(weapon_reload)
    
def apply_script(protocol, connection, config):
    class ZombiesProtocol(protocol):
        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.message_i = 0
            self.modes_loop = LoopingCall(self.modes_update)
            self.modes_loop.start(UPDATE_RATE)
            self.ZOMBIE_TELEPORT = 22
            self.ZOMBIE_HP = 1000
            self.spawnhigh = 14
            self.com = True
            
        def modes_update(self):
            self.message_i += UPDATE_RATE
            for player in self.players.values():
                if player.mode == HUMAN:
                    player.can_heal = True
                    player.health_message = True
            if self.message_i >= MESSAGE_UPDATE_RATE:
                self.message_i = 0
    
    class ZombiesConnection(connection):
        
        def get_direction(self):
            orientation = self.world_object.orientation
            angle = atan2(orientation.y, orientation.x)
            if angle < 0:
                angle += 6.283185307179586476925286766559
            # Convert to units of quadrents
            angle *= 0.63661977236758134307553505349006
            angle = round(angle)
            if angle == 4:
                angle = 0
            return angle
        
        def on_block_build_attempt(self, x, y, z):
            if self.mode == HUMAN and self.quickbuild_enabled == True:
                self.quickbuild_enabled = False
                self.create_explosion_effect(Vertex3(x,y,z))
                map = self.protocol.map
                block_action.value = BUILD_BLOCK
                block_action.player_id = self.player_id
                color = self.color + (255,)
                facing = self.get_direction()
                structure = QUICKBUILD_STRUCTURES[self.quickbuild]
                for block in structure:
                    bx = block[0]
                    by = block[1]
                    bz = block[2]
                    if facing == NORTH:
                        bx, by = bx, -by
                    elif facing == WEST:
                        bx, by = -by, -bx
                    elif facing == SOUTH:
                        bx, by = -bx, by
                    elif facing == EAST:
                        bx, by = by, bx
                    bx, by, bz = x+bx, y+by, z-bz
                    if (bx < 0 or bx >= 512 or by < 0 or by >= 512 or bz < 0 or
                        bz >= 62):
                        continue
                    if map.get_solid(bx, by, bz):
                        continue
                    block_action.x = bx
                    block_action.y = by
                    block_action.z = bz
                    self.protocol.send_contained(block_action, save = True)
                    map.set_point(bx, by, bz, color, user = False)
            elif self.mode == ZOMBIE:
                    return False
                    
            return connection.on_block_build_attempt(self, x, y, z)
        
        def create_explosion_effect(self, position):
            self.protocol.world.create_object(Grenade, 0.1, position, None, Vertex3(), None)
            grenade_packet.value = 0.0
            grenade_packet.player_id = 32
            grenade_packet.position = position.get()
            grenade_packet.velocity = (0.0, 0.0, 0.0)
            self.protocol.send_contained(grenade_packet)
        
        def on_block_destroy(self, x, y, z, value):
            if (self.mode == ZOMBIE and value == DESTROY_BLOCK and self.tool == SPADE_TOOL ):
                    map = self.protocol.map
                    ztel = self.protocol.ZOMBIE_TELEPORT
                    if (not map.get_solid(x, y, z-ztel+1) and not map.get_solid(x, y, z-ztel+2) and not map.get_solid(x, y, z-ztel+3)): 
                        player_location = self.world_object.position
                        self.create_explosion_effect(player_location)
                        loc = (player_location.x, player_location.y, player_location.z-ztel)
                        self.set_location(loc)
            return connection.on_block_destroy(self, x, y, z, value)
##            elif (self.mode == ZOMBIE and self.tool == WEAPON_TOOL):
##                return False
        
        def on_flag_capture(self):
            if self.team is self.protocol.green_team:
                self.mode = HUMAN
                self.refill()
                self.send_chat('YOU ARE HUMAN NOW RAWR GO SHOOT EM')
		self.protocol.send_chat('%s has become a human-zombie and can use weapons!' % self.name )
            return connection.on_flag_capture(self)
        

        
        def on_grenade(self, time_left):
            if self.mode == ZOMBIE:
                self.send_chat("Zombie! You fool! You forgot to unlock the grenade! It's useless now!")
                return False
            return connection.on_grenade(self, time_left)
        
        def on_hit(self, hit_amount, hit_player, type, grenade):
            new_hit = connection.on_hit(self, hit_amount, hit_player, type, grenade)
            if new_hit is not None:
                return new_hit

            other_player_location = hit_player.world_object.position
            other_player_location = (other_player_location.x, other_player_location.y, other_player_location.z)
            player_location = self.world_object.position
            player_location = (player_location.x, player_location.y, player_location.z)
            dist = floor(distance_3d(player_location, other_player_location))

            damagemulti = (sin(dist/80))+1
            new_hit = hit_amount * damagemulti

            if hit_player.mode == ZOMBIE and self.weapon == SMG_WEAPON:
                   new_hit = (new_hit/(self.protocol.ZOMBIE_HP/100))
                   if hit_player != self:
                       if new_hit >=25:
                           self.create_explosion_effect(hit_player.world_object.position)
                           self.send_chat("!!!HOLY SHIT UBER DAMAGE!!!")
            if hit_player.mode == ZOMBIE and self.weapon != SMG_WEAPON:
                   if self.weapon == SHOTGUN_WEAPON:
                       new_hit = new_hit/(self.protocol.ZOMBIE_HP/100)/8
                   else:
                       new_hit = new_hit/(self.protocol.ZOMBIE_HP/100)
                   if hit_player != self:
                       if new_hit >=25:
                           self.create_explosion_effect(hit_player.world_object.position)
                           self.send_chat("!!!HOLY SHIT UBER DAMAGE!!!")
            if self.mode == ZOMBIE and self.tool == WEAPON_TOOL:
                self.send_chat(" |    | \____/  \____/ \____/ |    | \____/ ")
                self.send_chat(" |   \| |    |  |  --\ |    | |   \|      \ ")
                self.send_chat(" |  \ | |    |  |      |    | |  \ | \____ ")
                self.send_chat(" |\   | /----\  /----\ |    | |\   | /----\ ")                
                return False
            if (self.mode == HUMAN and self.tool == SPADE_TOOL and 
                     self.team == hit_player.team and self.can_heal == True):
                   if hit_player.hp >= 100:
                       if self.health_message == True:
                           self.health_message = False
                           self.send_chat(hit_player.name + ' is at full health.')
                   elif hit_player.hp > 0:
                       self.can_heal = False
                       hit_player.set_hp(hit_player.hp + HEAL_RATE)
##            self.send_chat("The damage now is " + str(hit_amount))
            return new_hit
        
        def on_join(self):
            self.can_heal = False
            self.health_message = False
            self.quickbuild = 0
            self.quickbuild_points = 6
            self.quickbuild_enabled = False
            self.origin_block = None
            self.recorded_blocks = []
            
            return connection.on_join(self)
        
        def on_kill(self, killer, type, grenade):
            
            if self.team is self.protocol.green_team:
                self.mode = ZOMBIE
                empty_weapon( self )
                self.set_tool( SPADE_TOOL )
                
            if killer != None and killer != self:
                if killer.mode == HUMAN:
                    killer.quickbuild_points += 1
                    killer.refill()
                    killer.send_chat('You have been refilled!')
                else:
                    self.send_chat('THE ZOMBIES ARE COMING RAWRRR')
   
                    
                    #killer.set_hp(killer.hp + 25 - killer.hp/10)
                    #SETUP ZOMBIE BONUS HERE
            return connection.on_kill(self, killer, type, grenade)
        
        def on_spawn(self, pos):

                
            if self.team is self.protocol.green_team:
                if self.mode == HUMAN:
                    self.quickbuild_enabled = False
                    self.can_heal = True
                    self.health_message = True
                else:
                    #empty_weapon( self )
                    self.set_tool( SPADE_TOOL )
                
                self.send_chat('USE SPADE TO KILL')
                spawned = False
                
                if spawned == False and self.protocol.com == True:
                    spawned = True
                    player_location = self.world_object.position
                    loc = (player_location.x, player_location.y, float(int(player_location.z))+2.25)
                    self.set_location(loc)
                    self.create_explosion_effect( player_location )
                    
                else:
                    return False
                
            else:
                self.mode = HUMAN
            return connection.on_spawn(self, pos)
        
        def get_spawn_location(self):
            game_mode = self.protocol.game_mode
            if game_mode == TC_MODE:
                try:
                    if random.random() >0.25 or self.mode == HUMAN:
                        base = random.choice(list(self.team.get_entities()))
                    else:
                        base = random.choice(list(self.team.other.get_entities()))
                    return base.get_spawn_location()
                except IndexError:
                    pass


            return self.team.get_random_location(True)
    
        def on_tool_set_attempt(self, tool):
            if tool == WEAPON_TOOL and self.mode == ZOMBIE:
                        self.send_chat(
                            "You're a zombie you don't know how to use a gun! Take the spade!")
            return connection.on_tool_set_attempt(self, tool)
        
        def on_login(self, name):
            self.send_chat('Zombie health is '+str(self.protocol.ZOMBIE_HP)+' Zombie teleport '+str(self.protocol.ZOMBIE_TELEPORT)+' blocks high')
            if self.team is self.protocol.green_team:
                self.mode = ZOMBIE
                self.send_chat('#&*^%@#!*%&@#!*&@!#*%&!#@*% HEEEEY You are a ZOMBIE! Use the SPADE to kill humans. SPADE the ground to SUPER JUMP! You CAN NOT BUILD!')
            else:
                self.mode = HUMAN
                self.send_chat('You are a HUMAN! Use GUNS and GRENADES to kill zombies. Use the SPADE to heal other humans. Type /b to BUILD quickly. SMG has less damage!')
            return connection.on_login(self, name)
        def on_shoot_set(self, fire):
            if self.mode == ZOMBIE and self.tool == WEAPON_TOOL:
                if self.filter_visibility_data:
                    return
                self.send_chat("Only human zombies can use a gun! Take the spade!")
            return connection.on_shoot_set(self, fire)
        
                
    return ZombiesProtocol, ZombiesConnection
