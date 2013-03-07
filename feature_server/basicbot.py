# BASIC BOTS
# fakes a connection and partially replicates player behavior
# 
# pathfinding was stripped out since it is unfinished and depended
# on the C++ navigation module
# 
# requires adding the 'local' attribute to server.py's ServerConnection
# 
# *** 201,206 ****
# --- 201,207 ----
#       last_block = None
#       map_data = None
#       last_position_update = None
# +     local = False
#       
#       def __init__(self, *arg, **kw):
#           BaseConnection.__init__(self, *arg, **kw)
# *** 211,216 ****
# --- 212,219 ----
#           self.rapids = SlidingWindow(RAPID_WINDOW_ENTRIES)
#       
#       def on_connect(self):
# +         if self.local:
# +             return
#           if self.peer.eventData != self.protocol.version:
#               self.disconnect(ERROR_WRONG_VERSION)
#               return
# 
# bots should stare at you and pull the pin on a grenade when you get too close
# /addbot [amount] [green|blue]
# /toggleai
from inspect import *
from math import cos, sin, floor, atan2
import random
from enet import Address
from twisted.internet.reactor import seconds, callLater
from twisted.internet.task import LoopingCall
from pyspades.protocol import BaseConnection
from pyspades.server import parse_command, input_data, weapon_input, set_tool, chat_message, grenade_packet, hit_packet, block_line, block_action, set_color
from pyspades.world import Grenade
from pyspades.contained import *
from pyspades.common import Vertex3
from pyspades.collision import vector_collision, distance_3d, collision_3d
from pyspades.constants import *
from commands import admin, add, name, get_team, login

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
    
def point_distance2(c1, c2):
    if c1.world_object is not None and c2.world_object is not None:
        p1 = c1.world_object.position
        p2 = c2.world_object.position
        return (p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2
    
@name('aistate')
def ai_state(connection):
    return 'enabled' if connection.protocol.ai_enabled else 'disabled'
LOGIC_FPS = 4.0
@name('botstate')
def bot_state(connection, minbots = None, maxbots = None):
    
    if minbots is not None:
        if connection.min_bots < maxbots and minbots > 0:
            connection.min_bots = minbots
        else:
            return "min bots (%s) too low or greater then maxbots" % minbots
        
    if maxbots is not None:
        if maxbots <= connection.protocol.max_players and maxbots > connection.min_bots:
            connection.max_bots = maxbots
        else:
            return "max bots (%s) too high. Can't be less than minbots or higher than max players" % maxbots

    return "Bot stats :  %s bots %s  " % ( len(connection.protocol.bots) , ai_state(connection) )


@name('addbot')
def add_bot(connection, amount = None, team = None):

    protocol = connection.protocol
    if team:
        bot_team = get_team(connection, team)
    blue, green = protocol.blue_team, protocol.green_team
    amount = int(amount or 1)
    for i in xrange(amount):
        if not team:
            bot_team = blue if blue.count() < green.count() else green
        bot = protocol.add_bot(bot_team)
        if not bot:
            return "Added %s bot(s)" % i
        
    
    return "Added %s bot(s)" % amount



@name('toggleai')
def toggle_ai(connection):
    protocol = connection.protocol
    protocol.ai_enabled = not protocol.ai_enabled
    if not protocol.ai_enabled:
        for bot in protocol.bots:
            bot.flush_input()
    state = ai_state
    protocol.send_chat('AI %s!' % state )
    protocol.irc_say('* %s %s AI' % (connection.name, state))
    
add(bot_state)
add(add_bot)
add(ai_state)
add(toggle_ai)

class LocalPeer:
    #address = Address(None, 0)
    address = Address('255.255.255.255', 0)
    roundTripTime = 0.0
    
    def send(self, *arg, **kw):
        pass
    
    def reset(self):
        pass

def apply_script(protocol, connection, config):
    class BotProtocol(protocol):
        bots = None
        ai_enabled = True
        
        def add_bot(self, team):
            if len(self.connections) + len(self.bots) >= 32:
                return None
            bot = self.connection_class(self, None)
            bot.join_game(team)
            self.bots.append(bot)
            #bots login, so they can issue /commands
            # this will allow votes in votekicks etc
            # set up config.txt with a password for bots, and give them rights
            login( bot , 'ROBOTTOCH4N' )
            return bot
        
        def on_world_update(self):
            if self.bots and self.ai_enabled:
                do_logic = self.loop_count % int(UPDATE_FPS / LOGIC_FPS) == 0
                for bot in self.bots:
                    if do_logic:
                        bot.think()
                    bot.update()
            protocol.on_world_update(self)
        
        def on_map_change(self, map):
            self.bots = []
            protocol.on_map_change(self, map)
        
        def on_map_leave(self):
            for bot in self.bots[:]:
                bot.disconnect()
            self.bots = None
            protocol.on_map_leave(self)
            
        def update_master(self):
            if self.master_connection is None:
                return
            count = 0
            
            for connection in self.connections.values():
                if connection.player_id is not None:
                    count += 1

            count += len(self.bots)
            self.master_connection.set_count(count)
            
    class BotConnection(connection):
        aim = None
        aimed = None
        aim_at = None
        input = None
        acquire_targets = False
        grenade_call = None
        suicide_call = None
        
        reaim_call = False
        terminator = False # Don't get him angry
        ticks_fire = None
        fire_distance = None
        fire_tick_period = None
        # set these to allow min and max amount of bot players
        max_bots = 16
        min_bots = 0
        # allow bots to be kicked in favour of humans trying to join the server
        # /kick by a mod or admin will still work
        allow_kick = True 
        
        _turn_speed = None
        _turn_vector = None
        
        def _get_turn_speed(self):
            return self._turn_speed
        def _set_turn_speed(self, value):
            self._turn_speed = value
            self._turn_vector = Vertex3(cos(value), sin(value), 0.0)
        turn_speed = property(_get_turn_speed, _set_turn_speed)
        
        def __init__(self, protocol, peer):
            if peer is not None:
                return connection.__init__(self, protocol, peer)
            self.local = True
            user_type = 'admin'
            connection.__init__(self, protocol, LocalPeer())
            
            self.on_connect()
            #~ self.saved_loaders = None
            self._send_connection_data()
            self.send_map()
            
            self.aim = Vertex3()
            self.aimed = Vertex3()
            self.target_orientation = Vertex3()
            self.turn_speed = 0.15 # rads per tick
            self.ticks_fire = 42
            self.input = set()
        
        def join_game(self, team):
            self.name = 'AOSbot %s' % str(self.player_id)
            self.fire_distance = 80
            self.terminator = True
            self.fire_tick_period = 15
            self.team = team
            
            self.set_weapon( SMG_WEAPON, True)
            self.protocol.players[(self.name, self.player_id)] = self
            self.on_login(self.name)
            self.spawn()
        
        def disconnect(self, data = 0):
            if not self.local:
                return connection.disconnect(self)
            if self.disconnected:
                return
            self.protocol.bots.remove(self)
            self.disconnected = True
            self.on_disconnect()
        
        def think(self):
            obj = self.world_object
            pos = obj.position
            found = ()
                
            # find nearby foes
            if self.acquire_targets:
                for player in self.team.other.get_players():
                    if vector_collision(pos, player.world_object.position, 108.0):
                        if not self.aim_at:
                            if obj.can_see(*player.world_object.position.get()): 
                                self.aim_at = player
                        else:
                            if point_distance2(self, player) < point_distance2(self, self.aim_at):
                                if obj.can_see(*player.world_object.position.get()) and self.aim_at is not player:
                                    self.aim_at = player
                       
            if self.aim_at:
                
                self.acquire_targets = False
                dist = point_distance2(self, self.aim_at )

                if self.target_orientation.z < -0.25:

                    cont = block_line
                    cont.player_id = self.player_id
                    cont.x1 = (pos.x)
                    cont.y1 = (pos.y)
                    cont.z1 = (pos.z)
                    cont.x2 = (pos.x)
                    cont.y2 = (pos.y)
                    cont.z2 = (pos.z+2)

                    self.input.add("secondary_fire")

            if random.random() > 0.95 or self.aim_at is None:
                if self.team.other.flag.player is not self:
                    self.acquire_targets = True
                
            if self.aim_at and not obj.can_see(*self.aim_at.world_object.position.get()) and not self.terminator:
                self.aim_at = None
                
            # replicate player functionality
            if self.protocol.game_mode == CTF_MODE:
                
                other_flag = self.team.other.flag
                our_flag = self.team.flag
                if self.aim_at is None and our_flag.player and other_flag.player is not self:
                    self.aim_at = our_flag.player

                if self.aim_at is None and other_flag.player is self: 
                    self.aim.set_vector( self.team.base )
                    self.aim -= pos
                    distance_to_aim = self.aim.normalize() # don't move this line
                    self.target_orientation.set_vector(self.aim )
                    self.input.add("up")
                    
                elif other_flag.player is not self:
                    self.aim.set_vector( other_flag )
                    self.aim -= pos
                    distance_to_aim = self.aim.normalize() # don't move this line
                    self.target_orientation.set_vector(self.aim )
                    self.input.add("up")
                    
                if vector_collision(pos, self.team.base):
                    if other_flag.player is self:
                        self.capture_flag()
                    self.check_refill()
                    
                if not other_flag.player and vector_collision(pos, other_flag):
                    self.take_flag()

                    
            if self.hp < 30 and self.hp > 0 and self.terminator:
                if self.suicide_call is None:
                    self.set_tool( GRENADE_TOOL )
                    self.suicide_call = callLater(.2, self.suicide_grenade,
                        1.0)

            if random.random() >=0.15:
                self.input.add("secondary_fire")

                 
            if random.random() >=0.92 or self.target_orientation.z < -0.25:
                self.input.add("jump")
                if random.random() >=0.995:
                    self.on_block_destroy( pos.x, pos.y, pos.z, DESTROY_BLOCK )
                    
            player = self
            location = player.world_object.cast_ray( 3 )
            
            if location:
                px, py, pz = player.get_location()
                x, y, z = location
                map = player.protocol.map
                            
 
                if not collision_3d(px, py, pz, x, y, z, 3):
                    return
                self.input.add("primary_fire")
                if player.on_block_destroy(x, y, z, DESTROY_BLOCK) == False:
                    return
                if z > 62 or not destroy_block(player.protocol, x, y, z):
                    return
                if map.get_solid(x, y, z):
                    map.remove_point(x, y, z)
                    map.check_node(x, y, z, True)
                player.on_block_removed(x, y, z)
        
        def update(self):
            obj = self.world_object
            pos = obj.position
            ori = obj.orientation
            if not self.hp:
                self.flush_input()
                self.input.clear()
                return
            
            if self.aim_at and self.aim_at.world_object:
                aim_at_pos = self.aim_at.world_object.position

                # This will follow players line of sight
                #if self.aim_at.team.id == self.team.id:
                #    location = self.aim_at.world_object.cast_ray( 128 )
                #    if location:
                #        x, y, z = location
                #        aim_at_pos = Vertex3(x,y,z)
                    
                self.aim.set_vector(aim_at_pos)
                self.aim -= pos
                distance_to_aim = self.aim.normalize() # don't move this line
                # look at the target if it's within sight
                #if obj.can_see( *aim_at_pos.get() ):
                self.target_orientation.set_vector(self.aim)
                if self.team is self.protocol.blue_team:
                    if distance_to_aim < 20.0:
                        self.input.add("down")
                        
                # creeper behavior
                if  self.aim_at.team.id is not self.team.id and self.terminator:
                    if distance_to_aim < 36.0 and distance_to_aim > 24.0 and self.grenade_call is None and self.grenades > 2:
                        if random.random() >=0.9995:
                            self.set_tool( GRENADE_TOOL )
                            self.grenade_call = callLater(2.4 , self.throw_grenade,
                                1.4)

            # orientate towards target
            diff = ori - self.target_orientation
            diff.z = 0.0
            diff = diff.length_sqr()
            if diff > 0.001:
                p_dot = ori.perp_dot(self.target_orientation)
                if p_dot > 0.0:
                    ori.rotate(self._turn_vector)
                else:
                    ori.unrotate(self._turn_vector)
                new_p_dot = ori.perp_dot(self.target_orientation)
                if new_p_dot * p_dot < 0.0:
                    ori.set_vector(self.target_orientation)
                    if self.aim_at:
                        if obj.can_see( *self.aim_at.world_object.position.get() ) is not None:
                            self.reaim_call = True
                        else:
                            self.ticks_fire =0
    
            else:
                ori.set_vector(self.target_orientation)
                if self.grenade_call is None and self.suicide_call is None and 'down' not in self.input:
                    self.input.add("up")
                if self.aim_at:
                    if obj.can_see( *self.aim_at.world_object.position.get() ) is not None:
                        self.reaim_call = True
                    else:
                        self.ticks_fire = 0
           
            if self.aim_at and self.reaim_call == True:
                ppos = self.aim_at.world_object.position
                delta = pos - ppos
                if not delta.is_zero():
                
                    distance = delta.length()
                    r = self.world_object.cast_ray( distance )
                    
                    if r is None and self.ticks_fire >self.fire_tick_period and distance < self.fire_distance:
                        self.input.add("primary_fire")
                        self.input.discard("sprint")
                        self.aim_at.hit(  4, self, TORSO )
                        self.ticks_fire = 0
                    else:
                        self.ticks_fire +=1
                        
            if self.grenade_call or self.suicide_call:
                self.input.clear()
                self.input.add('primary_fire')
 
            obj.set_orientation(*ori.get())
            self.flush_input()
            
            #run if in the water

            #if self.aim_at is None:
            #    self.input.clear()
                
            
        def flush_input(self):


            
            input = self.input
            world_object = self.world_object
            z_vel = world_object.velocity.z
            if 'jump' in input and not (z_vel >= 0.0 and z_vel < 0.017):
                input.discard('jump')
            input_changed = not (
                ('up' in input) == world_object.up and
                ('down' in input) == world_object.down and
                ('left' in input) == world_object.left and
                ('right' in input) == world_object.right and
                ('jump' in input) == world_object.jump and
                ('crouch' in input) == world_object.crouch and
                ('sneak' in input) == world_object.sneak and
                ('sprint' in input) == world_object.sprint)
            if input_changed:
                if not self.freeze_animation:
                    world_object.set_walk('up' in input, 'down' in input,
                        'left' in input, 'right' in input)
                    world_object.set_animation('jump' in input, 'crouch' in input,
                        'sneak' in input, 'sprint' in input)
                if (not self.filter_visibility_data and
                    not self.filter_animation_data):
                    input_data.player_id = self.player_id
                    input_data.up = world_object.up
                    input_data.down = world_object.down
                    input_data.left = world_object.left
                    input_data.right = world_object.right
                    input_data.jump = world_object.jump
                    input_data.crouch = world_object.crouch
                    input_data.sneak = world_object.sneak
                    input_data.sprint = world_object.sprint
                    self.protocol.send_contained(input_data)
            primary = 'primary_fire' in input
            secondary = 'secondary_fire' in input
            shoot_changed = not (
                primary == world_object.primary_fire and
                secondary == world_object.secondary_fire)
            if shoot_changed:
                if primary != world_object.primary_fire:
                    if self.tool == WEAPON_TOOL:
                        self.weapon_object.set_shoot(primary)
                    if self.tool == WEAPON_TOOL or self.tool == SPADE_TOOL:
                        self.on_shoot_set(primary)
                world_object.primary_fire = primary
                world_object.secondary_fire = secondary
                if not self.filter_visibility_data:
                    weapon_input.player_id = self.player_id
                    weapon_input.primary = primary
                    weapon_input.secondary = secondary
                    self.protocol.send_contained(weapon_input)
            input.clear()
            


            
        def suicide_grenade(self, time_left):
            self.suicide_call = None
            
            if not self.hp or not self.grenades:
                return
            self.grenades -= 1
            if self.on_grenade(time_left) == False:
                return
            obj = self.world_object
            orient = obj.orientation
            orient.z-=.2
            grenade = self.protocol.world.create_object(Grenade, time_left,
                obj.position, None, orient, self.grenade_exploded)
            grenade.team = self.team
            self.on_grenade_thrown(grenade)
            if self.filter_visibility_data:
                return
            grenade_packet.player_id = self.player_id
            grenade_packet.value = time_left
            grenade_packet.position = grenade.position.get()
            grenade_packet.velocity = grenade.velocity.get()
            self.protocol.send_contained(grenade_packet)
            
        def throw_grenade(self, time_left):
            self.grenade_call = None
            
            if not self.hp or not self.grenades:
                return
            
            self.grenades -= 1
            if self.on_grenade(time_left) == False:
                return
            self.input.add("jump")
            obj = self.world_object
            orient = obj.orientation
            # aim up a little
            orient.z-=.29
            grenade = self.protocol.world.create_object(Grenade, time_left,
                obj.position, None, orient, self.grenade_exploded)
            grenade.team = self.team
            self.on_grenade_thrown(grenade)
            if self.filter_visibility_data:
                return
            grenade_packet.player_id = self.player_id
            grenade_packet.value = time_left
            grenade_packet.position = grenade.position.get()
            grenade_packet.velocity = grenade.velocity.get()
            self.protocol.send_contained(grenade_packet)
            self.set_tool( WEAPON_TOOL )
                
        def on_spawn(self, pos):
            
            if not self.local:
                return connection.on_spawn(self, pos )
            self.world_object.set_orientation(1.0, 0.0, 0.0)
            self.aim.set_vector(self.world_object.orientation)
            self.target_orientation.set_vector(self.aim)

            self.acquire_targets = False
            self.aim_at = None
            self.input.add("jump")
            
            return connection.on_spawn(self, pos )
        
        
        def on_kill(self, killer, type, grenade):
            if not self.local:
               connection.on_kill(self, killer, type, grenade)
            if random.random() >0.9:
                cont = chat_message
                cont.player_id = self.player_id
                cont.chat_type = 0
                
                if self.terminator is True:
                    self.on_command(*parse_command("lightning"))

                cont.value = 'I will eat your Brain'
                #self.protocol.send_contained( cont, False, sender = self )
            
            connection.on_kill(self, killer, type, grenade)
            
        def set_tool(self, tool):
            if self.on_tool_set_attempt(tool) == False:
                return
            self.tool = tool
            if self.tool == WEAPON_TOOL:
                self.on_shoot_set(self.world_object.primary_fire)
                self.weapon_object.set_shoot(self.world_object.secondary_fire)
            self.on_tool_changed(self.tool)
            if self.filter_visibility_data:
                return
            set_tool.player_id = self.player_id
            set_tool.value = self.tool
            self.protocol.send_contained(set_tool)


        def on_connect(self):
            protocol = self.protocol

            if self.local:
                if len(protocol.bots) > self.max_bots:
                    return self.disconnect()
                else:
                    return connection.on_connect(self)
            
            max_players = min(32, protocol.max_players)
            

            
            if len(protocol.connections) + len(protocol.bots) > max_players:
                if not self.allow_kick:
                    return self.disconnect(ERROR_FULL)
                elif len(protocol.bots) > self.min_bots:
                    # let's try getting rid of a bot
                    try:
                        protocol.bots[-1].disconnect( ERROR_KICKED )
                        return connection.on_connect(self)
                    except IndexError:
                        return self.disconnect(ERROR_FULL)
                

            connection.on_connect(self)
        
        def on_disconnect(self):
            for bot in self.protocol.bots:
                if bot.aim_at is self:
                    bot.aim_at = None
                    bot.aquire_targets = True
                    
            connection.on_disconnect(self)
        

        
        def _send_connection_data(self):
            if self.local:
                if self.player_id is None:
                    self.player_id = self.protocol.player_ids.pop()
                return
            connection._send_connection_data(self)
        
        def send_map(self, data = None):
            if self.local:
                self.on_join()
                return
            connection.send_map(self, data)
            

        def timer_received(self, value):
            if self.local:
                return
            connection.timer_received(self, value)
        
        def send_loader(self, loader, ack = False, byte = 0):
            if self.local:
                return
            return connection.send_loader(self, loader, ack, byte)
        

                
    return BotProtocol, BotConnection
