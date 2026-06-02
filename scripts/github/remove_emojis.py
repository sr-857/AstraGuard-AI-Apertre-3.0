import sys
import re

def main():
    emojis_to_remove = [
        "🌟", "🏆", "📋", "📊", "🎖️", "🏅", "🚀", "🛡️", "🧠", "🎓", "✅", "👨‍💻", "🏗️", "🔧", "🛰️", 
        "⚡", "🎯", "🔍", "📈", "🌐", "📂", "👥", "👋", "📚", "💡", "📞", "📄", "💝", "❤️", "🐛", 
        "✨", "💬", "💻", "📝", "🎨", "🧪", "⚙️", "🔬", "✍️", "🌍", "🤝", "🔒", "🎉", "💪", "👑", 
        "🌈", "🎁", "🙏"
    ]
    
    try:
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()
            
        for emoji in emojis_to_remove:
            content = content.replace(emoji + " ", "")
            content = content.replace(" " + emoji, "")
            content = content.replace(emoji, "")
            
        with open('README.md', 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("Successfully removed emojis from README.md")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
