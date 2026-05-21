import re

with open("frontend/components/visualizations/DynamicChart.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Make the outer container of the standalone dynamic chart softer.
content = content.replace('className="w-full h-full flex flex-col p-4"', 'className="w-full h-full flex flex-col p-6 bg-white dark:bg-slate-900 rounded-xl"')

with open("frontend/components/visualizations/DynamicChart.tsx", "w", encoding="utf-8") as f:
    f.write(content)
