import re

with open("components/agent/ChatInterface.tsx", "r") as f:
    text = f.read()

target = """                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  )}"""

repl = """                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  )}
                  
                  {/* SQL Viewer */}
                  {msg.metadata?.sql && (
                    <SQLViewer sql={msg.metadata.sql} />
                  )}"""

text = text.replace(target, repl)

with open("components/agent/ChatInterface.tsx", "w") as f:
    f.write(text)

