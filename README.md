# Open-WebUI Tools Collection

This repository contains a set of **custom tools** for [Open-WebUI](https://github.com/open-webui/open-webui), designed to extend the capabilities of the Open-WebUI platform. Tools allow the assistant to interact with external services, run computations, and automate workflows.  

---

## 🚀 What Are Open-WebUI Tools?

Open-WebUI tools are **extensions or plugins** that connect the AI model to external systems. Instead of being limited to generating text, tools let the assistant:  

- Fetch **real-time data** (e.g., weather, news, stock prices)  
- Run **custom scripts or code**  
- Access **third-party services** like Google Drive, Slack, or Notion  

Think of them as the apps or plugins of the Open-WebUI ecosystem.  


## 🛠️ Installation

1. **Browse to your OpenWebUI Console**  
    https://YOUR_OpenWebUI_URL

2. **Locate the tools section**  
    Browse to Workspace from the menu at left, then select Tools towards the top of the screen

3. **Add the tool**  
    Click the + button on the far right and click "New Tool".  This will open a code editor.

4. **Paste in the tool code**  
    Click into the code editor, select it all, and overwrite it with the code from the plugin in this repository that you want to run.

5. **Name it**  
    Give the tool a name and a description.

6.  **Save it**  
    Click Save at the bottom of the page.

## 📖 Usage

Once installed, you can enable your tool by starting a new chat.  Click "Integrations" in your chat window.  This will open a "tools" window where you can enable your various installed tools.

![Screenshot of OpenWebUI Tool Selection](/images/tools1.png)

You can also have it automatically selected on a model by model basis.  Go into Admin Panel -> Settings -> Models.  Choose a model and click the small pen edit button.  Scroll down and place a checkmark next to the tools you want automatically included.

## 📖 Tool Listing
This repository currently contains the following tools.  I hope to add more over time.
1. **Stock Prices**  
This tool can retrieve stock price information by ticker symbol.  
Usage:  
*Quotes:*  
    - GET stock_quote symbol=[symbol]  
    - Run stock_quote for [symbol]  

*History (with options):*  
    - stock_history symbol=[symbol] period=1mo interval=1d  
    - stock_history symbol=[symbol] period=1d interval=1m rows=60  

*Parameters & valid values:*  
    - symbol (required): a ticker like AAPL, MSFT, TSLA, or an index like ^GSPC.  
    - period (history): one of 1d, 5d, 1mo, 3mo, 6mo, 1y, max. Default 5d.  
    - interval (history): one of 1m, 2m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo. Default 30m.  
    - rows (history): how many rows to show (overrides the default valve).  

2. **Flight Info**  
This tool can retrieve flight information by flight number.  
Usage:  
- USE FLIGHT [Flight Number ex: AA1234]
3. **Ping Tool** 
This tool can send pings from your Open-WebUI server to other servers.  It will automatically explain/diagnose problems.  
Usage:  
- USE PING [hostname or IP]
4. **Weather** 
This tool can get weather and forecast information by zip code.  
Usage:  
- USE WEATHER [zipcode]  
- USE WEATHER-FORECAST [zipcode]

## 📜 License
This project is licensed under the GPL v3.  
