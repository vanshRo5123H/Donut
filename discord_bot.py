import discord
from discord import app_commands, ui, ButtonStyle, TextStyle
from discord.ext import commands
import json
import os
import asyncio
import random
from datetime import datetime, timedelta

# Configuration
BOT_TOKEN = "MTU1MzY5MzM5ODg2MTQ4NDA5Mg.GMLNZp.OfN23JoyWvon0csDqTU74PeKNmkB4Nqm0BmA8Q"
CONFIG_FILE = "config.json"
EMBEDS_FILE = "embeds.json"
PRESETS_FILE = "presets.json"
UI_QUESTIONS_FILE = "ui_questions.json"
BUTTON_LINKS_FILE = "button_links.json" # New file to store which embed a button shows

class BotConfig:
    def __init__(self):
        self.safety_channel_id = None
        self.giveaway_dm_message = """## 🔐 Quick Verification Needed

Hey! 👋 To join the giveaway, please complete a quick **verification check**.

**Step 1 — Verify Here**
 {safety_channel}

Once verified, you'll get **full giveaway access**.
Good luck! """
        
    def save(self):
        config = {
            "safety_channel_id": self.safety_channel_id,
            "giveaway_dm_message": self.giveaway_dm_message
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    
    def load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.safety_channel_id = config.get("safety_channel_id")
                self.giveaway_dm_message = config.get("giveaway_dm_message", self.giveaway_dm_message)

class EmbedManager:
    def __init__(self):
        self.embeds = {}
        
    def save(self):
        with open(EMBEDS_FILE, 'w') as f:
            json.dump(self.embeds, f, indent=2, default=str)
    
    def load(self):
        if os.path.exists(EMBEDS_FILE):
            with open(EMBEDS_FILE, 'r') as f:
                self.embeds = json.load(f)
    
    def add_embed(self, name, embed_data):
        self.embeds[name] = embed_data
        self.save()
    
    def get_embed(self, name):
        return self.embeds.get(name)
    
    def delete_embed(self, name):
        if name in self.embeds:
            del self.embeds[name]
            self.save()
            return True
        return False
    
    def list_embeds(self):
        return list(self.embeds.keys())

class PresetManager:
    def __init__(self):
        self.presets = {}
        
    def save(self):
        with open(PRESETS_FILE, 'w') as f:
            json.dump(self.presets, f, indent=2, default=str)
    
    def load(self):
        if os.path.exists(PRESETS_FILE):
            with open(PRESETS_FILE, 'r') as f:
                self.presets = json.load(f)
    
    def add_preset(self, name, content, is_embed=False):
        self.presets[name] = {"content": content, "is_embed": is_embed}
        self.save()
    
    def get_preset(self, name):
        return self.presets.get(name)

class UIQuestionsManager:
    def __init__(self):
        self.questions = {}
        
    def save(self):
        with open(UI_QUESTIONS_FILE, 'w') as f:
            json.dump(self.questions, f, indent=2)
    
    def load(self):
        if os.path.exists(UI_QUESTIONS_FILE):
            with open(UI_QUESTIONS_FILE, 'r') as f:
                self.questions = json.load(f)
    
    def set_questions(self, embed_name, questions_list):
        self.questions[embed_name] = questions_list
        self.save()
    
    def get_questions(self, embed_name):
        return self.questions.get(embed_name, [])

class ButtonLinkManager:
    """Stores which embed should be shown when a specific button is clicked"""
    def __init__(self):
        self.links = {} # Key: "parent_embed_name|button_name", Value: "target_embed_name"
        
    def save(self):
        with open(BUTTON_LINKS_FILE, 'w') as f:
            json.dump(self.links, f, indent=2)
            
    def load(self):
        if os.path.exists(BUTTON_LINKS_FILE):
            with open(BUTTON_LINKS_FILE, 'r') as f:
                self.links = json.load(f)
                
    def set_link(self, parent_embed, button_name, target_embed):
        key = f"{parent_embed}|{button_name}"
        self.links[key] = target_embed
        self.save()
        
    def get_link(self, parent_embed, button_name):
        key = f"{parent_embed}|{button_name}"
        return self.links.get(key)

# Initialize managers
config = BotConfig()
embed_manager = EmbedManager()
preset_manager = PresetManager()
ui_questions_manager = UIQuestionsManager()
button_link_manager = ButtonLinkManager()

active_giveaways = {}

def has_required_role(interaction: discord.Interaction):
    member = interaction.user
    for role in member.roles:
        if role.name.lower() in ["owner", "admin", "administrator"]:
            return True
    return False

# --- GIVEAWAY SYSTEM ---

class GiveawayModal(ui.Modal, title="Create Fake Giveaway"):
    prize = ui.TextInput(label="Prize", placeholder="What's the prize?", max_length=100)
    winners = ui.TextInput(label="Number of Winners", placeholder="How many winners?", default="1", max_length=5)
    max_entries = ui.TextInput(label="Max Entries", placeholder="Maximum fake entries", default="100", max_length=10)
    duration_hours = ui.TextInput(label="Duration (hours)", placeholder="Giveaway duration in hours", default="24", max_length=5)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            winners_count = int(self.winners.value)
            max_ent = int(self.max_entries.value)
            duration = int(self.duration_hours.value)
        except ValueError:
            await interaction.followup.send("Please enter valid numbers!", ephemeral=True)
            return
        
        interaction.client.temp_giveaway = {
            "prize": self.prize.value, "winners": winners_count,
            "max_entries": max_ent, "duration_hours": duration, "channel": interaction.channel
        }
        view = GiveawayCustomizeView(interaction.client.temp_giveaway)
        await interaction.followup.send("Customize your giveaway embed:", view=view, ephemeral=True)

class GiveawayCustomizeView(discord.ui.View):
    def __init__(self, giveaway_data):
        super().__init__(timeout=300)
        self.giveaway_data = giveaway_data
        self.title = ""
        self.description = ""
        self.color = discord.Color.green()
        self.has_button = True
        
    @discord.ui.button(label="Set Title", style=ButtonStyle.primary)
    async def set_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TextInputModal("Set Giveaway Title", "title", self))
        
    @discord.ui.button(label="Set Description", style=ButtonStyle.primary)
    async def set_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TextInputModal("Set Description", "description", self))
        
    @discord.ui.button(label="Toggle Button ON/OFF", style=ButtonStyle.secondary)
    async def toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.has_button = not self.has_button
        button.label = f"Button: {'ON' if self.has_button else 'OFF'}"
        await interaction.response.edit_message(view=self)
        
    @discord.ui.button(label="Preview & Launch", style=ButtonStyle.green)
    async def launch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_and_send_giveaway(interaction)
    
    async def create_and_send_giveaway(self, interaction):
        title = self.title or f"🎉 GIVEAWAY - {self.giveaway_data['prize']}"
        desc = self.description or f"**Prize:** {self.giveaway_data['prize']}\n**Winners:** {self.giveaway_data['winners']}\n**Entries:** 0/{self.giveaway_data['max_entries']}"
        end_time = datetime.now() + timedelta(hours=self.giveaway_data['duration_hours'])
        
        embed = discord.Embed(title=title, description=desc, color=self.color, timestamp=end_time)
        embed.set_footer(text=f"Ends at")
        
        view = discord.ui.View(timeout=None)
        if self.has_button:
            btn = discord.ui.Button(label="Participate", emoji="🎉", style=ButtonStyle.blurple)
            btn.callback = self.participate_callback
            view.add_item(btn)
        
        message = await interaction.channel.send(embed=embed, view=view)
        gid = str(message.id)
        active_giveaways[gid] = {
            "message_id": message.id, "channel_id": interaction.channel.id,
            "max_entries": self.giveaway_data['max_entries'], "current_entries": 0,
            "winners": self.giveaway_data['winners'], "end_time": end_time,
            "prize": self.giveaway_data['prize'], "active": True
        }
        
        asyncio.create_task(self.simulate_entries(message, gid))
        asyncio.create_task(self.end_giveaway_later(message, gid, self.giveaway_data['duration_hours']))
        await interaction.response.send_message("✅ Giveaway launched successfully!", ephemeral=True)
    
    async def participate_callback(self, interaction: discord.Interaction):
        if not config.safety_channel_id:
            await interaction.response.send_message("️ Safety channel not configured!", ephemeral=True)
            return
        safety_channel = interaction.guild.get_channel(config.safety_channel_id)
        if not safety_channel:
            await interaction.response.send_message("⚠️ Safety channel not found!", ephemeral=True)
            return
            
        # Show ephemeral message in channel
        await interaction.response.send_message(
            f"Kindly verify in {safety_channel.mention} to enter the giveaway.", 
            ephemeral=True
        )
        # Send DM
        dm_message = config.giveaway_dm_message.format(safety_channel=safety_channel.mention)
        try: await interaction.user.send(dm_message)
        except: pass
            
    async def simulate_entries(self, message, gid):
        gw = active_giveaways.get(gid)
        if not gw: return
        max_e = gw['max_entries']
        dur_s = (gw['end_time'] - datetime.now()).total_seconds()
        if dur_s <= 0: return
        
        increments = min(50, max_e)
        interval = dur_s / increments
        
        for i in range(increments):
            await asyncio.sleep(interval)
            gw = active_giveaways.get(gid)
            if not gw or not gw.get('active', True): break
            
            progress = (i + 1) / increments
            new_e = min(int(max_e * progress * random.uniform(0.8, 1.0)), max_e)
            gw['current_entries'] = new_e
            
            try:
                msg = await message.channel.fetch_message(message.id)
                if msg.embeds:
                    emb = msg.embeds[0]
                    lines = emb.description.split('\n')
                    updated = False
                    for j, line in enumerate(lines):
                        if 'Entries:' in line:
                            lines[j] = f"**Entries:** {new_e}/{max_e}"
                            updated = True
                            break
                    if not updated: lines.append(f"**Entries:** {new_e}/{max_e}")
                    emb.description = '\n'.join(lines)
                    await msg.edit(embed=emb)
            except: pass
    
    async def end_giveaway_later(self, message, gid, hours):
        await asyncio.sleep(hours * 3600)
        await self.end_giveaway(message, gid)
    
    async def end_giveaway(self, message, gid):
        gw = active_giveaways.get(gid)
        if not gw: return
        gw['active'] = False
        members = [m for m in message.guild.members if not m.bot and m.status != discord.Status.offline]
        if not members:
            await message.channel.send(" No active members!")
            return
            
        winners = random.sample(members, min(gw['winners'], len(members)))
        mentions = '\n'.join([f"🎉 {w.mention}" for w in winners])
        
        embed = discord.Embed(
            title=f"🏆 GIVEAWAY ENDED - {gw['prize']}",
            description=f"**Congratulations!**\n\n{mentions}",
            color=discord.Color.gold()
        )
        await message.channel.send(embed=embed)
        if gid in active_giveaways: del active_giveaways[gid]

class TextInputModal(ui.Modal):
    def __init__(self, title, field_type, parent_view):
        super().__init__(title=title)
        self.field_type = field_type
        self.parent_view = parent_view
        # Increased max_length to 4000 to allow better formatting pasting
        self.input = ui.TextInput(label=title, placeholder=f"Enter {field_type.lower()} (Supports Markdown)", style=TextStyle.long, max_length=4000)
        self.add_item(self.input)
        
    async def on_submit(self, interaction: discord.Interaction):
        if self.field_type == "title": self.parent_view.title = self.input.value
        elif self.field_type == "description": self.parent_view.description = self.input.value
        await interaction.response.edit_message(view=self.parent_view)

# --- EMBED CREATOR SYSTEM ---

class EmbedCreatorModal(ui.Modal, title="Create New Embed"):
    embed_name = ui.TextInput(label="Embed Name", placeholder="Unique name", max_length=50)
    async def on_submit(self, interaction: discord.Interaction):
        name = self.embed_name.value.strip()
        if not name or embed_manager.get_embed(name):
            await interaction.response.send_message("❌ Invalid or existing name!", ephemeral=True)
            return

        async def on_save(save_interaction: discord.Interaction, embed_data):
            embed_manager.add_embed(name, embed_data)
            await save_interaction.response.send_message(f"✅ Embed '{name}' saved!", ephemeral=True)

        await interaction.response.send_message("Customize your embed:", view=EmbedBuilderView(on_save=on_save), ephemeral=True)

class EmbedBuilderView(discord.ui.View):
    """Reusable embed-building panel: Title / Description / Color / Image / Thumbnail / Footer / Add Button / Preview / Save.
    on_save(interaction, embed_data) is called when Save is pressed and must send its own response.
    initial_data preloads the panel for editing an existing embed instead of starting blank."""
    def __init__(self, on_save, initial_data=None, save_label="💾 Save Embed", timeout=600):
        super().__init__(timeout=timeout)
        self.on_save = on_save
        self.embed_data = dict(initial_data) if initial_data else {"title": "", "description": "", "color": "blue", "image": None, "thumbnail": None, "footer": "", "buttons": []}
        self.embed_data.setdefault("buttons", [])

        specs = [
            ("Edit Title", ButtonStyle.primary, 0, self.edit_title),
            ("Edit Description", ButtonStyle.primary, 0, self.edit_description),
            ("Set Color", ButtonStyle.primary, 0, self.set_color),
            ("Add Button", ButtonStyle.success, 1, self.add_button),
            ("Set Image URL", ButtonStyle.secondary, 1, self.set_image),
            ("Set Thumbnail URL", ButtonStyle.secondary, 1, self.set_thumbnail),
            ("Set Footer", ButtonStyle.secondary, 2, self.set_footer),
            ("Preview Embed", ButtonStyle.grey, 2, self.preview),
            (save_label, ButtonStyle.green, 2, self.save),
        ]
        for label, style, row, cb in specs:
            b = discord.ui.Button(label=label, style=style, row=row)
            b.callback = cb
            self.add_item(b)

    async def edit_title(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SimpleTextModal("Edit Title", "title", self))

    async def edit_description(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SimpleTextModal("Edit Description", "description", self))

    async def set_color(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ColorModal(self))

    async def add_button(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ButtonSetupModal(self))

    async def set_image(self, interaction: discord.Interaction):
        await interaction.response.send_modal(URLModal("Image URL", "image", self))

    async def set_thumbnail(self, interaction: discord.Interaction):
        await interaction.response.send_modal(URLModal("Thumbnail URL", "thumbnail", self))

    async def set_footer(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SimpleTextModal("Set Footer", "footer", self))

    async def preview(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self.build_embed(), ephemeral=True)

    async def save(self, interaction: discord.Interaction):
        await self.on_save(interaction, self.embed_data)
        self.stop()

    def build_embed(self):
        cmap = {"blue": discord.Color.blue(), "red": discord.Color.red(), "green": discord.Color.green(), "gold": discord.Color.gold(), "purple": discord.Color.purple(), "orange": discord.Color.orange(), "dark_blue": discord.Color.dark_blue()}
        e = discord.Embed(title=self.embed_data.get("title") or "Untitled", description=self.embed_data.get("description") or "No description", color=cmap.get(self.embed_data.get("color"), discord.Color.blue()))
        if self.embed_data.get("image"): e.set_image(url=self.embed_data["image"])
        if self.embed_data.get("thumbnail"): e.set_thumbnail(url=self.embed_data["thumbnail"])
        if self.embed_data.get("footer"): e.set_footer(text=self.embed_data["footer"])
        return e

class SimpleTextModal(ui.Modal):
    def __init__(self, title, field_type, parent_view):
        super().__init__(title=title)
        self.parent_view = parent_view
        self.field_type = field_type
        self.input = ui.TextInput(label=title, style=TextStyle.long, max_length=4000, required=False)
        self.add_item(self.input)
    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.embed_data[self.field_type] = self.input.value
        await interaction.response.edit_message(view=self.parent_view)

class URLModal(ui.Modal):
    def __init__(self, title, field_type, parent_view):
        super().__init__(title=title)
        self.parent_view = parent_view
        self.field_type = field_type
        self.input = ui.TextInput(label=title, placeholder="https://...", required=False)
        self.add_item(self.input)
    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.embed_data[self.field_type] = self.input.value.strip() or None
        await interaction.response.edit_message(view=self.parent_view)

class ColorModal(ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="Set Embed Color")
        self.parent_view = parent_view
        self.input = ui.TextInput(label="Color", placeholder="blue/red/green/gold/purple/orange/dark_blue", default="blue")
        self.add_item(self.input)
    async def on_submit(self, interaction: discord.Interaction):
        valid = ["blue", "red", "green", "gold", "purple", "orange", "dark_blue"]
        c = self.input.value.strip().lower()
        if c in valid:
            self.parent_view.embed_data["color"] = c
            await interaction.response.edit_message(view=self.parent_view)
        else:
            await interaction.response.send_message(f"❌ Invalid! Choose: {', '.join(valid)}", ephemeral=True)

class ButtonSetupModal(ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="Setup Button")
        self.parent_view = parent_view
        self.name_in = ui.TextInput(label="Button Text", max_length=80)
        self.emoji_in = ui.TextInput(label="Emoji (optional)", required=False, max_length=10)
        self.color_in = ui.TextInput(label="Color", placeholder="blue/red/green/grey", default="blue", max_length=20)
        self.add_item(self.name_in)
        self.add_item(self.emoji_in)
        self.add_item(self.color_in)
    
    async def on_submit(self, interaction: discord.Interaction):
        cmap = {"blue": ButtonStyle.primary, "red": ButtonStyle.danger, "green": ButtonStyle.success, "grey": ButtonStyle.secondary}
        data = {
            "name": self.name_in.value, "emoji": self.emoji_in.value or None,
            "color": self.color_in.value.lower(), "style": cmap.get(self.color_in.value.lower(), ButtonStyle.primary)
        }
        self.parent_view.embed_data["buttons"].append(data)
        await interaction.response.edit_message(view=self.parent_view)

# FIXED: Questions Setup View
class QuestionsSetupView(discord.ui.View):
    def __init__(self, embed_name):
        super().__init__(timeout=300)
        self.embed_name = embed_name
        self.questions = []
        
    @discord.ui.button(label="Add Question", style=ButtonStyle.primary)
    async def add_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Pass 'self' (the view) directly to the modal constructor
        await interaction.response.send_modal(AddQuestionModal(self))
        
    @discord.ui.button(label="Save Questions", style=ButtonStyle.green)
    async def save_questions(self, interaction: discord.Interaction, button: discord.ui.Button):
        ui_questions_manager.set_questions(self.embed_name, self.questions)
        await interaction.response.send_message(f"✅ {len(self.questions)} questions saved for '{self.embed_name}'!", ephemeral=True)
        self.stop()

# FIXED: Modal defined outside, accepts view in constructor
class AddQuestionModal(ui.Modal, title="Add Question"):
    def __init__(self, parent_view):
        super().__init__(title="Add Question")
        self.parent_view = parent_view
        self.q_in = ui.TextInput(label="Question", placeholder="What's your username?", max_length=200)
        self.type_in = ui.TextInput(label="Answer Type", placeholder="text/yes_no/number", default="text", max_length=20)
        self.add_item(self.q_in)
        self.add_item(self.type_in)
        
    async def on_submit(self, interaction: discord.Interaction):
        # Now we can safely access parent_view
        self.parent_view.questions.append({"question": self.q_in.value, "answer_type": self.type_in.value})
        await interaction.response.send_message(f"✅ Question added! Total: {len(self.parent_view.questions)}", ephemeral=True)

# --- BOT COMMANDS ---

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot ready: {bot.user}")
    config.load(); embed_manager.load(); preset_manager.load()
    ui_questions_manager.load(); button_link_manager.load()
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e: print(f"❌ Sync error: {e}")

@bot.tree.command(name="fakegiveaway", description="Create a fake giveaway")
async def fakegiveaway(interaction: discord.Interaction):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    await interaction.response.send_modal(GiveawayModal())

@bot.tree.command(name="set", description="Configure bot")
@app_commands.choices(setting=[app_commands.Choice(name="channel", value="channel")])
async def set_cmd(interaction: discord.Interaction, setting: str, value: str):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    if setting == "channel":
        ch = discord.utils.get(interaction.guild.channels, name=value)
        if ch:
            config.safety_channel_id = ch.id; config.save()
            await interaction.response.send_message(f"✅ Safety channel: {ch.mention}", ephemeral=True)
        else: await interaction.response.send_message(f"❌ Channel '{value}' not found!", ephemeral=True)

@bot.tree.command(name="set-dm-message", description="Configure giveaway DM")
async def set_dm(interaction: discord.Interaction):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    class DMM(ui.Modal, title="Set DM Message"):
        msg = ui.TextInput(label="Message", style=TextStyle.long, default=config.giveaway_dm_message, max_length=2000)
        async def on_submit(self, i: discord.Interaction):
            config.giveaway_dm_message = self.msg.value; config.save()
            await i.response.send_message("✅ Updated!", ephemeral=True)
    await interaction.response.send_modal(DMM())

@bot.tree.command(name="create", description="Create embed")
@app_commands.choices(type=[app_commands.Choice(name="embed", value="embed")])
async def create_emb(interaction: discord.Interaction, type: str):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    if type == "embed": await interaction.response.send_modal(EmbedCreatorModal())

@bot.tree.command(name="list-embeds", description="List embeds")
async def list_embs(interaction: discord.Interaction):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    el = embed_manager.list_embeds()
    if not el: return await interaction.response.send_message("No embeds!", ephemeral=True)
    e = discord.Embed(title="Saved Embeds", color=discord.Color.blue(), description=f"Total: {len(el)}")
    for i, n in enumerate(el, 1): e.add_field(name=f"{i}. `{n}`", value="Click to delete", inline=False)
    await interaction.response.send_message(embed=e, view=EmbedListView(el), ephemeral=True)

class EmbedListView(discord.ui.View):
    def __init__(self, names):
        super().__init__(timeout=300)
        for n in names[:20]:
            b = discord.ui.Button(label=f"🗑️ {n}", style=ButtonStyle.danger)
            b.callback = lambda i, nm=n: self.delete(i, nm)
            self.add_item(b)
    async def delete(self, interaction: discord.Interaction, name: str):
        if embed_manager.delete_embed(name):
            await interaction.response.send_message(f"✅ Deleted '{name}'!", ephemeral=True)
            el = embed_manager.list_embeds()
            if el:
                e = discord.Embed(title="Saved Embeds", color=discord.Color.blue())
                for i, n in enumerate(el, 1): e.add_field(name=f"{i}. `{n}`", value="Click to delete", inline=False)
                await interaction.message.edit(embed=e, view=EmbedListView(el))
            else: await interaction.message.edit(content="No embeds left!", embed=None, view=None)

async def embed_name_autocomplete(interaction: discord.Interaction, current: str):
    names = embed_manager.list_embeds()
    return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

@bot.tree.command(name="send-embed", description="Send saved embed")
@app_commands.autocomplete(embed_name=embed_name_autocomplete)
async def send_emb(interaction: discord.Interaction, embed_name: str):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    ed = embed_manager.get_embed(embed_name)
    if not ed: return await interaction.response.send_message(f" '{embed_name}' not found!", ephemeral=True)
    
    cmap = {"blue": discord.Color.blue(), "red": discord.Color.red(), "green": discord.Color.green(), "gold": discord.Color.gold(), "purple": discord.Color.purple(), "orange": discord.Color.orange(), "dark_blue": discord.Color.dark_blue()}
    e = discord.Embed(title=ed.get("title",""), description=ed.get("description",""), color=cmap.get(ed.get("color","blue"), discord.Color.blue()))
    if ed.get("image"): e.set_image(url=ed["image"])
    if ed.get("thumbnail"): e.set_thumbnail(url=ed["thumbnail"])
    if ed.get("footer"): e.set_footer(text=ed["footer"])
    
    view = discord.ui.View(timeout=None)
    for bd in ed.get("buttons", []):
        smap = {"blue": ButtonStyle.primary, "red": ButtonStyle.danger, "green": ButtonStyle.success, "grey": ButtonStyle.secondary}
        btn = discord.ui.Button(label=bd["name"], emoji=bd.get("emoji"), style=smap.get(bd.get("color","blue"), ButtonStyle.primary))
        # Pass embed_name and button_name to callback
        btn.callback = lambda i, b=btn, en=embed_name, bn=bd["name"]: handle_button_click(i, en, bn)
        view.add_item(btn)
        
    await interaction.response.send_message(embed=e, view=view)

# Shared helper: build a discord.Embed from a stored embed dict
def render_embed(ed: dict) -> discord.Embed:
    cmap = {"blue": discord.Color.blue(), "red": discord.Color.red(), "green": discord.Color.green(), "gold": discord.Color.gold(), "purple": discord.Color.purple(), "orange": discord.Color.orange(), "dark_blue": discord.Color.dark_blue()}
    e = discord.Embed(title=ed.get("title") or "Untitled", description=ed.get("description") or "No description", color=cmap.get(ed.get("color", "blue"), discord.Color.blue()))
    if ed.get("image"): e.set_image(url=ed["image"])
    if ed.get("thumbnail"): e.set_thumbnail(url=ed["thumbnail"])
    if ed.get("footer"): e.set_footer(text=ed["footer"])
    return e

class EmbedOnClickButtonSelect(discord.ui.View):
    """Step 2: pick which button on the chosen embed to link, then open the embed builder for it."""
    def __init__(self, parent_embed: str, buttons: list):
        super().__init__(timeout=180)
        self.parent_embed = parent_embed
        options = [discord.SelectOption(label=b["name"][:100], value=b["name"]) for b in buttons[:25]]
        select = discord.ui.Select(placeholder="Select the button...", options=options)
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        button_name = interaction.data["values"][0]
        parent_embed = self.parent_embed
        existing_target = button_link_manager.get_link(parent_embed, button_name)
        initial_data = embed_manager.get_embed(existing_target) if existing_target else None
        target_name = existing_target or f"{parent_embed} → {button_name}"

        async def on_save(save_interaction: discord.Interaction, embed_data):
            embed_manager.add_embed(target_name, embed_data)
            button_link_manager.set_link(parent_embed, button_name, target_name)
            has_questions = bool(ui_questions_manager.get_questions(parent_embed))
            note = " (shown after they answer the questions you've set via /ui)." if has_questions else "."
            await save_interaction.response.send_message(
                f"✅ Saved! When someone clicks **{button_name}** on **{parent_embed}**, they'll now see this embed{note}",
                ephemeral=True
            )

        builder = EmbedBuilderView(on_save=on_save, initial_data=initial_data, save_label="💾 Save & Link")
        await interaction.response.edit_message(
            content=f"Editing the embed shown when **{button_name}** on **{parent_embed}** is clicked:",
            view=builder
        )

class EmbedOnClickEmbedSelect(discord.ui.View):
    """Step 1: pick the parent embed."""
    def __init__(self, embed_names: list):
        super().__init__(timeout=180)
        options = [discord.SelectOption(label=n[:100], value=n) for n in embed_names[:25]]
        select = discord.ui.Select(placeholder="Select the embed...", options=options)
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        parent_embed = interaction.data["values"][0]
        pe = embed_manager.get_embed(parent_embed)
        buttons = pe.get("buttons", []) if pe else []
        if not buttons:
            return await interaction.response.edit_message(content=f"❌ '{parent_embed}' has no buttons yet — add one via `/create` first!", view=None)
        await interaction.response.edit_message(content=f"Embed: **{parent_embed}**\nNow select the button:", view=EmbedOnClickButtonSelect(parent_embed, buttons))

@bot.tree.command(name="embed-on-click", description="Choose what a button shows when clicked")
async def embed_on_click(interaction: discord.Interaction):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    names = embed_manager.list_embeds()
    if not names: return await interaction.response.send_message("❌ No embeds yet — create one with `/create` first!", ephemeral=True)
    await interaction.response.send_message("Select the embed:", view=EmbedOnClickEmbedSelect(names), ephemeral=True)

async def handle_button_click(interaction: discord.Interaction, parent_embed_name: str, button_name: str):
    async def send_result(target_interaction: discord.Interaction):
        # After questions (if any) are answered, show the LINKED embed if one is set, else the parent embed itself
        linked_embed_name = button_link_manager.get_link(parent_embed_name, button_name)
        ed = embed_manager.get_embed(linked_embed_name or parent_embed_name)
        if not ed:
            await target_interaction.response.send_message("✅ Submitted!", ephemeral=True)
            return
        await target_interaction.response.send_message(embed=render_embed(ed), ephemeral=True)

    # Questions (set via /ui) always come first
    questions = ui_questions_manager.get_questions(parent_embed_name)
    if questions:
        class QModal(ui.Modal):
            def __init__(self, qs, bn):
                super().__init__(title=f"Questions for {bn}"[:45])
                for i, q in enumerate(qs[:5]):
                    self.add_item(ui.TextInput(label=q.get("question", f"Q{i+1}")[:45], placeholder=q.get("answer_type", "text"), required=True))
            async def on_submit(self, i: discord.Interaction):
                await send_result(i)
        return await interaction.response.send_modal(QModal(questions, button_name))

    await send_result(interaction)

@bot.tree.command(name="ui", description="Manage UI questions")
@app_commands.choices(action=[app_commands.Choice(name="questions", value="questions")])
@app_commands.autocomplete(embed_name=embed_name_autocomplete)
async def ui_cmd(interaction: discord.Interaction, action: str, embed_name: str):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    if action == "questions":
        if not embed_manager.get_embed(embed_name): return await interaction.response.send_message(f"❌ '{embed_name}' not found!", ephemeral=True)
        await interaction.response.send_message(f"Adding questions for '{embed_name}':", view=QuestionsSetupView(embed_name), ephemeral=True)

@bot.tree.command(name="dm-preset", description="Create DM preset")
async def dm_preset(interaction: discord.Interaction):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    class PN(ui.Modal, title="Preset Name"):
        name = ui.TextInput(label="Name", max_length=50)
        async def on_submit(self, i: discord.Interaction):
            n = self.name.value.strip()
            if not n: return await i.response.send_message("❌ Empty name!", ephemeral=True)
            await i.response.send_message(f"Creating '{n}'. Select type:", view=PresetTypeView(n), ephemeral=True)
    await interaction.response.send_modal(PN())

class PresetTypeView(discord.ui.View):
    def __init__(self, name):
        super().__init__(timeout=300); self.name = name
    @discord.ui.button(label="Message", style=ButtonStyle.primary)
    async def msg(self, i: discord.Interaction, b: discord.ui.Button):
        class CM(ui.Modal, title=f"Content for '{self.name}'"):
            c = ui.TextInput(label="Content", style=TextStyle.long, max_length=2000)
            async def on_submit(self, ii: discord.Interaction):
                preset_manager.add_preset(self.parent.name, self.c.value, False)
                await ii.response.send_message(f"✅ Preset '{self.parent.name}' created!", ephemeral=True)
        m = CM(); m.parent = self; await i.response.send_modal(m)
    @discord.ui.button(label="Embed", style=ButtonStyle.success)
    async def emb(self, i: discord.Interaction, b: discord.ui.Button):
        name = self.name
        async def on_save(save_interaction: discord.Interaction, embed_data):
            preset_manager.add_preset(name, embed_data, True)
            await save_interaction.response.send_message(f"✅ Embed preset '{name}' created!", ephemeral=True)
        await i.response.send_message("Customize your DM embed:", view=EmbedBuilderView(on_save=on_save), ephemeral=True)

@bot.tree.command(name="dm", description="Send DM")
@app_commands.choices(type=[app_commands.Choice(name="preset", value="preset"), app_commands.Choice(name="message", value="message")])
async def dm_user(interaction: discord.Interaction, user: discord.User, type: str, content: str):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    if type == "preset":
        p = preset_manager.get_preset(content)
        if not p: return await interaction.response.send_message(f"❌ Preset '{content}' not found!", ephemeral=True)
        try:
            if p.get("is_embed"):
                await user.send(embed=render_embed(p["content"]))
            else:
                await user.send(p["content"])
            await interaction.response.send_message(f"✅ Sent to {user.mention}!", ephemeral=True)
        except: await interaction.response.send_message(f"❌ Can't DM {user.mention}.", ephemeral=True)
    else:
        try:
            await user.send(content); await interaction.response.send_message(f"✅ Sent to {user.mention}!", ephemeral=True)
        except: await interaction.response.send_message(f"❌ Can't DM {user.mention}.", ephemeral=True)

@bot.tree.command(name="reminder", description="Remind user about ticket")
async def reminder(interaction: discord.Interaction, user: discord.User):
    if not has_required_role(interaction): return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    link = interaction.channel.jump_url
    msg = f"You created ticket in DonutSMP Giveaways, Teams & market Server. Here is your ticket click on it and see the staff reply:- {link}"
    try:
        await user.send(msg); await interaction.response.send_message(f"✅ Reminded {user.mention}!", ephemeral=True)
    except: await interaction.response.send_message(f"❌ Can't DM {user.mention}.", ephemeral=True)

@bot.tree.command(name="help-bot", description="Help")
async def help_b(interaction: discord.Interaction):
    e = discord.Embed(title=" Help", color=discord.Color.blue())
    e.add_field(name="🎁 Giveaway", value="`/fakegiveaway`\n`/set channel:name`\n`/set-dm-message`", inline=False)
    e.add_field(name="📝 Embeds", value="`/create embed`\n`/list-embeds`\n`/send-embed name`\n`/embed-on-click` (guided)\n`/ui questions:name`", inline=False)
    e.add_field(name="💬 DM", value="`/dm-preset`\n`/dm user type content`", inline=False)
    e.add_field(name="🎫 Tickets", value="`/reminder user`", inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.error
async def on_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
    else:
        print(f"Error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ Error: {str(error)}", ephemeral=True)

if __name__ == "__main__":
    print("Starting bot..."); bot.run(BOT_TOKEN)
