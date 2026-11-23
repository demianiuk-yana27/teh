import json
import os
import threading
import uuid
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API = ""  # Configured Apps Script /exec URL; no Cloudflare or Render
CONFIG = Path(os.environ.get("APPDATA") or Path.home()) / "TehQuickRequests" / "settings.json"
MANAGERS = ["Тех М'якота Владислав","Тех Кріпак Дар'я","Тех Часовська Софія","Тех Дем'янюк Яна","Тех Лагода Наталія","Тех Чернявська Валерія","Тех Русак Тетяна","Тех Скобельська Інна","Тех Гаврилюк Ярослав","Тех Шонія Анастасія","Тех Лесечко Світлана","Тех Васьковець Ольга","Тех Кейван Влада","Тех Братівник Ганна","Тех Мороз Галина"]
TAGS = {"2 Відділ":["Інше","На вайбер (месенджери)","Оформити","Рахунок/ додаткові дії","Цікавить/консультація","ОПТ собі"],"Тех":["Інше","Оф чати геткол","Обʼєднання замовлень","Питання по замовленню","Дооформити розетка","Пропущений","Бот приїхала"]}
CHANGES = ["Зміна суми наложки","Зняття наложки","Повернення посилки","Зміна отримувача","Оплата доставки/Зміна платника","Переадресація","Продовжити термін зберігання","Скасувати повернення","Зміна номера"]

def load():
    try: return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError): return {}

def save(data):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

class App:
    def __init__(self, root):
        self.root=root
        self.root.title("🐿️ Тех.Відділ — Швидкі запити")
        self.root.geometry("390x530")
        self.root.minsize(350,490)
        self.root.resizable(True,True)
        self.settings=load()
        self.mode=tk.StringVar(value="Бурундуки")
        self.tab=tk.StringVar(value=self.settings.get("tab","2 Відділ"))
        self.manager=tk.StringVar(value=self.settings.get("manager",""))
        self.top=tk.BooleanVar(value=False)
        self.fields={}
        self.busy=False
        self.frame=ttk.Frame(root,padding=(12,9))
        self.frame.pack(fill="both",expand=True)
        self.render()

    @staticmethod
    def layout_independent_shortcuts(widget):
        """Use Windows virtual key codes so Ctrl+V works with Ukrainian layout."""
        shortcuts={65:"<<SelectAll>>",67:"<<Copy>>",86:"<<Paste>>",88:"<<Cut>>"}
        def on_key(event):
            # Windows virtual-key codes are independent of the active keyboard layout.
            # Avoid treating AltGr (Ctrl+Alt) as a shortcut.
            if (event.state & 0x4) and not (event.state & 0x8):
                action=shortcuts.get(event.keycode)
                if action:
                    if event.keycode==65:
                        if isinstance(widget,tk.Text):
                            widget.tag_add("sel","1.0","end-1c")
                        else:
                            widget.selection_range(0,"end")
                            widget.icursor("end")
                    else:
                        widget.event_generate(action)
                    return "break"
        widget.bind("<KeyPress>",on_key,add="+")

    def render(self):
        for child in self.frame.winfo_children():child.destroy()
        self.fields={}
        ttk.Label(self.frame,text="Швидка подача запитів",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,5))
        modes=ttk.Frame(self.frame);modes.pack(fill="x",pady=(0,5))
        for mode in ("Бурундуки","Зміни з ТТН"):
            ttk.Radiobutton(modes,text=("🐿️ " if mode=="Бурундуки" else "📦 ")+mode,variable=self.mode,value=mode,command=self.render).pack(side="left",padx=(0,10))
        if self.mode.get()=="Бурундуки":
            self.combo("tab","Вкладка",["2 Відділ","Тех","Опт/дроп"],self.tab,lambda _:self.render())
        self.combo("manager","Менеджер",MANAGERS,self.manager)
        if self.mode.get()=="Бурундуки":
            if self.tab.get()=="Опт/дроп":
                self.combo("kind","Тип запиту",["Опт","Дроп"])
                self.entry("number","Номер замовлення або телефону")
            else:
                self.entry("number","Номер телефону або замовлення")
                self.combo("tag","Мітка запиту",TAGS[self.tab.get()])
        else:
            self.entry("order","Номер замовлення")
            self.entry("ttn","Номер ТТН")
            self.combo("error","Чия помилка?",["Менеджера","Прохання клієнта","Нічия"])
            self.combo("change","Тип зміни",CHANGES)
        ttk.Label(self.frame,text="Суть запиту").pack(anchor="w",pady=(5,2))
        self.description=tk.Text(self.frame,height=3,wrap="word",font=("Segoe UI",10))
        self.description.pack(fill="x")
        self.layout_independent_shortcuts(self.description)
        ttk.Checkbutton(self.frame,text="Поверх інших вікон",variable=self.top,command=lambda:self.root.attributes("-topmost",self.top.get())).pack(anchor="w",pady=(5,2))
        self.send=ttk.Button(self.frame,text="Подати запит",command=self.submit)
        self.send.pack(fill="x",ipady=3,pady=(3,5))
        self.status=tk.StringVar(value="Готово до надсилання")
        ttk.Label(self.frame,textvariable=self.status,wraplength=350,foreground="#25634d").pack(anchor="w")
        ttk.Button(self.frame,text="Налаштувати підключення до Google",command=self.configure_key).pack(anchor="w",pady=(5,0))

    def combo(self,key,title,options,variable=None,changed=None):
        ttk.Label(self.frame,text=title).pack(anchor="w",pady=(4,1))
        var=variable or tk.StringVar()
        box=ttk.Combobox(self.frame,textvariable=var,values=options,state="readonly")
        box.pack(fill="x")
        if not var.get() and options:box.set(options[0] if key not in ("manager",) else "")
        if changed:box.bind("<<ComboboxSelected>>",changed)
        self.fields[key]=var

    def entry(self,key,title):
        ttk.Label(self.frame,text=title).pack(anchor="w",pady=(8,3))
        var=tk.StringVar()
        input_widget=ttk.Entry(self.frame,textvariable=var)
        input_widget.pack(fill="x")
        self.layout_independent_shortcuts(input_widget)
        self.fields[key]=var

    def configure_key(self):
        dialog=tk.Toplevel(self.root)
        dialog.title("Google Apps Script — підключення")
        dialog.geometry("560x245")
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog,text="Адреса вебзастосунку Google Apps Script (/exec):").pack(anchor="w",padx=15,pady=(15,5))
        endpoint=tk.StringVar(value=self.settings.get("endpoint",""))
        endpoint_entry=ttk.Entry(dialog,textvariable=endpoint)
        endpoint_entry.pack(fill="x",padx=15)
        self.layout_independent_shortcuts(endpoint_entry)
        ttk.Label(dialog,text="Ключ доступу (Script Properties → QUICK_REQUESTS_KEY):").pack(anchor="w",padx=15,pady=(12,5))
        key=tk.StringVar(value=self.settings.get("key",""))
        entry=ttk.Entry(dialog,textvariable=key,show="*")
        entry.pack(fill="x",padx=15)
        self.layout_independent_shortcuts(entry)
        def accept():
            url=endpoint.get().strip()
            secret=key.get().strip()
            if not (url.startswith("https://script.google.com/macros/s/") and url.endswith("/exec")):
                messagebox.showerror("Невірна адреса","Вставте URL Google Apps Script, що закінчується на /exec.",parent=dialog)
                return
            if len(secret)<32:
                messagebox.showerror("Ключ","Ключ має містити щонайменше 32 символи.",parent=dialog)
                return
            self.settings.update(endpoint=url,key=secret)
            save(self.settings)
            dialog.destroy()
        ttk.Button(dialog,text="Зберегти",command=accept).pack(pady=15)

    def submit(self):
        if self.busy:return
        v={key:var.get().strip() for key,var in self.fields.items()}
        desc=self.description.get("1.0","end").strip()
        if self.mode.get()=="Бурундуки":
            wholesale=self.tab.get()=="Опт/дроп"
            values=[v.get("manager",""),v.get("kind","") if wholesale else v.get("number",""),v.get("number","") if wholesale else desc,desc if wholesale else v.get("tag","")]
            mode="requests"
        else:
            values=[v.get("manager",""),v.get("order",""),v.get("ttn",""),desc,v.get("error",""),v.get("change","")]
            mode="ttn"
        if not all(values):
            messagebox.showwarning("Не всі поля", "Заповніть усі поля.");return
        if not self.settings.get("key") or not self.settings.get("endpoint"):
            self.configure_key()
            if not self.settings.get("key") or not self.settings.get("endpoint"):return
        self.settings.update(manager=self.manager.get(),tab=self.tab.get())
        save(self.settings)
        self.busy=True;self.send.configure(state="disabled");self.status.set("Надсилаємо…")
        payload=json.dumps({"mode":mode,"tab":self.tab.get(),"values":values,"key":self.settings["key"],"requestId":str(uuid.uuid4())},ensure_ascii=False).encode("utf-8")
        def worker():
            try:
                req=Request(self.settings["endpoint"],data=payload,headers={"Content-Type":"text/plain;charset=utf-8"},method="POST")
                with urlopen(req,timeout=35) as response:
                    result=json.loads(response.read().decode("utf-8"))
                if result.get("unverified"):
                    msg="⚠️ Перевірте таблицю перед повторним надсиланням: "+result.get("message","")
                    clear=False
                elif result.get("ok"):
                    msg="✅ Записано: "+result.get("sheetName","")+" — "+result.get("updatedRange","")
                    clear=True
                else:raise ValueError(result.get("error","Невідома помилка"))
            except HTTPError as exc:
                raw = exc.read(4096).decode("utf-8", errors="replace")
                try:
                    data = json.loads(raw)
                    detail = data.get("error") or data.get("message") or ""
                except ValueError:
                    detail = ""
                if exc.code == 403:
                    msg = ("❌ HTTP 403: Google відхилив запит. "
                           + (str(detail)[:160] if detail else
                              "Перевірте доступ до Google Apps Script."))
                elif exc.code == 401:
                    msg = "❌ HTTP 401: Доступ до Google Apps Script не дозволено. Перевірте налаштування публікації."
                else:
                    msg = "❌ HTTP " + str(exc.code) + (": " + str(detail)[:180] if detail else "")
                clear=False
            except (URLError,TimeoutError,ValueError,OSError) as exc:
                msg="❌ "+str(exc);clear=False
            self.root.after(0,lambda:self.done(msg,clear))
        threading.Thread(target=worker,daemon=True).start()

    def done(self,msg,clear):
        self.busy=False;self.send.configure(state="normal");self.status.set(msg)
        if clear:
            for key,var in self.fields.items():
                if key not in ("manager","tab"):var.set("")
            self.description.delete("1.0","end")

if __name__=="__main__":
    root=tk.Tk()
    try:ttk.Style().theme_use("vista")
    except tk.TclError:pass
    App(root)
    root.mainloop()
