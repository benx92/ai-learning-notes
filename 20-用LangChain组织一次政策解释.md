# 大模型应用开发学习 20：用LangChain组织一次政策解释

商城想在售后页面增加一个功能：用户输入问题，系统根据适用的政策给出解释。

用户可能问“会员订单的申请期限是多少”，也可能问“商品收到十天了，应该先核对哪些退货条件”。运营维护的是政策文字，用户使用自己的说法提问。产品希望回答能够结合条款讲清楚期限与例外，并说明哪些条件还需要核对。

如果只要展示一条固定期限，程序查配置、返回文字就够了。这里使用模型的背景是：资料可能较长、问法各不相同，需要把已经取得的条款解释给用户。模型负责组织解释，应用负责给它适用资料、安排调用并展示结果。

**这篇要解决的是：怎样把“准备输入→请求模型→取出回答”做成一段能够反复使用的功能。**先把这三个步骤讲清楚，再讨论框架帮助组织了什么。并行、异步等扩展需求单独放在文末链接，不必先学完才能运行这个功能。

**配套仓库与代码入口**

完整仓库：[benx92/ai-learning-notes](https://github.com/benx92/ai-learning-notes)。本篇代码都在[`examples/20-lcel`](https://github.com/benx92/ai-learning-notes/tree/main/examples/20-lcel)目录，读正文时可以先打开基础入口，再按需查看复用组件和扩展实验：

| 文件或说明 | 负责什么 | 建议什么时候看 |
| --- | --- | --- |
| [basic_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/basic_demo.py) | 逐步调用、整链调用、空问题直接返回 | **先看、先运行这个文件**，对应正文主线 |
| [chain_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/chain_demo.py) | 提供政策数据、模板、模型创建函数和基础链；保留字段映射、并行、分支与流式实验 | 正文提到某个复用函数时查看；其余实验按需读 |
| [reliability_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/reliability_demo.py) | 模拟临时超时后的有限重试、持续失败后的备用处理 | 需要理解失败处理时查看 |
| [test_examples.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/test_examples.py) | 检查调用次数、数据交接、空问题拦截及扩展组件行为 | 运行示例后核对验证范围 |
| [requirements.txt](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/requirements.txt) | 本例固定的直接依赖版本 | 安装环境时使用 |
| [README](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/README.md) | 完整命令、预期现象、在线配置与示例边界 | 运行遇到问题时查阅 |
| [组件组合与运行方式扩展](https://github.com/benx92/ai-learning-notes/blob/main/supplements/20-组件组合与运行方式扩展.md) | 保留并行、字段追加、批量、异步、流式等详细讲解 | 基础主线读通后，按需求选择主题 |

`basic_demo.py`会导入`chain_demo.py`中的已有函数，运行时请保留整个示例目录，不要只复制单个文件。默认使用固定回复，不需要API Key；在线模式的配置与验证边界在文末说明。

首次下载时，在准备保存项目的目录执行：

```powershell
git clone https://github.com/benx92/ai-learning-notes.git
cd ai-learning-notes
cd examples/20-lcel
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe basic_demo.py
```

已有仓库直接进入examples/20-lcel，使用安装好依赖的环境即可。正文中的Python调用片段在该目录的Python会话或另存的脚本中运行；标明源码的函数是完整文件的摘录。首次阅读也可以直接运行basic_demo.py，不必逐段复制。

## 从页面收到的问题，到用户看到的回答

为了观察程序，我们使用两份固定教学条款：普通订单签收后7日内可以申请退货，会员订单是15日；商品例外仍要另行核对。它们只是教学资料，不代表真实平台政策。

假设应用已经取得本次适用的会员条款，用户问：

> 会员订单的申请期限是多少？

一次处理需要下面几份数据：

| 时刻 | 程序手里有什么 | 接下来要做什么 |
| --- | --- | --- |
| 开始 | 会员条款、用户问题 | 告诉模型要解释哪些资料、回答什么 |
| 输入准备好 | 处理要求和两份具体内容组成的聊天消息 | 请求模型 |
| 响应返回 | 包含回答的消息对象 | 取出回答文字 |
| 最后 | 一段普通字符串 | 展示给用户 |

这几个步骤存在先后依赖。没有把条款发给模型，就不能把回答当作本次政策解释；模型没有返回结果，也就没有文字可以展示。

```text
已有的适用政策 + 用户问题
          ↓
组织成发给模型的消息
          ↓
请求模型生成解释
          ↓
从回复中取出文字
          ↓
展示给用户
```

资料从哪里来，是这条流程的上游问题：可以从经过确认的配置、文档或检索结果中取得。本例直接读取本地字典，先集中观察取得资料以后的处理。它不查询订单，也不决定某笔订单最终能否退货。

普通Python完全能安排这些步骤。先不考虑任何框架，把它写成流程示意就是：

<!-- example-kind: illustration -->

```python
def explain_policy(policy, question):
    messages = prepare_input(policy, question)
    reply = call_model(messages)
    return read_answer(reply)
```

这里的三个内部函数名只是表达职责的示意，下面会用实际组件完成同样的事。我们需要先看懂功能本身，才能判断采用框架是否省事。

## 第一步：把资料与问题放进一份固定格式

每次请求都会变化的是条款和问题，基本要求则保持一致。例如：只解释提供的资料，不猜测具体订单资格，不代替用户提交申请。

如果每次调用都重新拼接这些文字，很容易漏掉资料或要求。程序可以保留一份固定格式，每次只填入当前内容。这份固定格式称为**提示模板**。

LangChain提供`ChatPromptTemplate`创建聊天消息模板。下面是[chain_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/chain_demo.py)里的实际函数：

<!-- example-source: examples/20-lcel/chain_demo.py -->

```python
def make_prompt():
    # make_prompt是本例自定义函数；ChatPromptTemplate是框架提供的模板组件。
    # from_messages根据“角色+文字格式”创建模板，不是向模型发送消息。
    # 步骤1：声明消息格式；{context}和{question}到invoke时才填入。
    # 创建模板不会请求模型，也不会检索资料。
    return ChatPromptTemplate.from_messages([
        # system保存处理要求；human中的两个占位符接收本次资料与问题。
        ("system", "只解释提供的教学政策，不判断具体订单资格，不查询或提交申请。"),
        ("human", "资料：{context}\n问题：{question}"),
    ])
```

`ChatPromptTemplate`是框架提供的组件名；`.from_messages(...)`表示根据给出的消息格式创建模板。`make_prompt()`则是我们自己定义的函数名，用来集中保存这段创建代码。

这里有两条消息。`system`那条放固定要求；`human`那条放本次资料和问题。`{context}`与`{question}`是留待填写的位置，其中`context`在本例里就是政策文字。创建模板时，还没有填入具体内容，也没有请求模型。

例如实际传入的是：

<!-- example-kind: usage -->

```python
from chain_demo import POLICIES, make_prompt

inputs = {
    "context": POLICIES["member"],  # 从教学字典取得会员条款。
    "question": "会员订单的申请期限是多少？",
}
prompt = make_prompt()  # 创建固定格式。
prepared = prompt.invoke(inputs)  # 把字典里的两个值填到对应位置。
for message in prepared.to_messages():
    print(message.content)  # 看清模型将收到什么，不调用模型。
```

第二条消息会包含这两项内容：

```text
资料：教学政策：会员订单签收后15日内可以申请退货，商品例外需另行核对。来源：demo-policy/member。
问题：会员订单的申请期限是多少？
```

`invoke`在这里表示“执行这个组件的工作”：模板的工作是填写消息，所以模板的invoke不会生成回答。`prepared`保存填好的输入；框架给这种输入对象起的类型名是`ChatPromptValue`。不必先记住类型名，先确认它里面确实有本次条款和问题。

## 第二步与第三步：请求模型，再取出回复文字

输入准备好了，才把它交给模型调用对象。下面接着使用上一段的`prepared`：

<!-- example-kind: usage -->

```python
from chain_demo import make_model

model = make_model()  # 本例默认创建离线固定回复对象。
reply = model.invoke(prepared)  # 请求一轮回复，得到消息对象。
print(type(reply).__name__)  # AIMessage：这是响应消息的类型名。
print(reply.content)  # 当前纯文本消息里的回答文字。
```

在线应用中，`model`通常是连接某个模型服务的客户端对象。它的invoke会请求服务，模型根据收到的资料组织回答。为了先观察程序，本例默认交回一段预设文字，不请求网络，也不理解用户问题：

```text
教学固定响应：会员订单的申请期限为签收后15日，商品例外仍需核对。
```

所以离线修改问题或条款，不会让这句回答自动跟着变化。这个替身只帮助我们核对执行和数据交接；真实模型能否正确解释，需要在线单独验证。

`reply`是一条消息对象。除了文本，一条响应还可能带有工具请求或用量信息；当前只需要展示回答，因此读取`reply.content`就能取得本例字符串。到这里，一次政策解释的三个步骤已经走通了。

配套[基础入口basic_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/basic_demo.py)把刚才的实际调用放进同一个普通Python函数：

<!-- example-source: examples/20-lcel/basic_demo.py -->

```python
def run_stepwise(model, context, question):
    # 第一步：把已经取得的政策和用户问题放进模板，得到模型输入。
    inputs = {"context": context, "question": question}
    prompt = make_prompt()
    prepared = prompt.invoke(inputs)
    # 第二步：请求模型；默认离线时，这里只取得预设回复。
    reply = model.invoke(prepared)
    # 第三步：本例回复是纯文本消息，直接读取content字段里的回答。
    return reply.content
```

它接收模型对象、已经取得的条款和问题，返回回答文字。页面处理代码可以调用这个函数，客服后台也可以调用它。**普通函数已经能实现复用，这一点不需要框架组合语法才能做到。**

## 把三步交给共同的执行方式，究竟改变了什么

现在考虑我们维护的不只是政策解释，还可能有文档摘要、邮件整理等功能。它们的输入内容和要求不同，却经常有“准备输入、请求模型、整理输出”这样的步骤。

希望把其中一些步骤作为现成组件重复组合，并通过相近的方法运行时，框架的共同执行接口开始有用。它让一个步骤能放进一条链，一条已经组装好的链也能作为另一个流程中的步骤。

LangChain把遵循这种共同接口的组件称为**Runnable**。它可以接收输入、执行处理、返回结果。刚才的模板和模型都属于这种组件，所以都有invoke；但它们接收和返回的数据仍不同。

为了把“取出文字”也接进这种组合，LangChain提供`StrOutputParser`。这个名字表示输出为字符串的解析组件，它读取已有响应里的文本，不会再次请求模型，也不检查回答是否符合政策。当前纯文本情况下，它取得的文字与`reply.content`一致：

<!-- example-kind: usage -->

```python
from langchain_core.output_parsers import StrOutputParser

parser = StrOutputParser()  # 创建负责取文字的组件。
answer = parser.invoke(reply)  # 处理刚才已经收到的消息。
print(answer == reply.content)  # True：当前纯文本例子中，两种取法相同。
```

三个步骤现在都能参与共同的组合。于是可以写成：

<!-- example-kind: usage -->

```python
# 使用前面创建的三个对象；这一行只建立连接关系。
chain = prompt | model | parser
# 这行才开始执行：填模板 -> 请求模型 -> 取出文字。
answer = chain.invoke(inputs)
print(answer)
```

这里的`|`表示从左到右连接：左边的结果交给右边。框架把这种组合写法称为**LCEL**，全名是LangChain Expression Language。它是Python对象的组合方式，不是另外发给模型理解的一段语言。

可以把两种实际写法逐项对上：

| 原来自己逐步调用 | 组合后的内部步骤 |
| --- | --- |
| `prompt.invoke(inputs)` | 第一个组件准备输入 |
| `model.invoke(prepared)` | 第二个组件接收准备好的输入并取得响应 |
| `parser.invoke(reply)` | 第三个组件接收响应，交回文字 |

如果希望多处使用同样的组合，源码里的函数把它返回给调用方：

<!-- example-source: examples/20-lcel/chain_demo.py -->

```python
def build_basic_chain(model):
    # 模板负责准备输入；解析器只提取文本，不再次调用模型。
    prompt = make_prompt()
    # StrOutputParser是组件类名；加()创建对象，保存到自定义变量parser中。
    # 它把AIMessage中的文本交给下一步；当前纯文本例子也可以直接读reply.content。
    parser = StrOutputParser()
    # 步骤1 -> 步骤2 -> 步骤3：填模板 -> 调模型 -> 从响应中取出文本。
    # 这里只建立连接；chain.invoke(inputs)才会真正按顺序执行。
    return prompt | model | parser
```

`build_basic_chain(model)`创建连接关系，返回的`chain`仍然可以用invoke执行，也能继续参与其他组合。它的具体类型名是`RunnableSequence`，对应的就是“依次执行这些步骤”。[官方组合接口](https://reference.langchain.com/python/langchain-core/runnables/base/RunnableSequence)

这次变化并没有提高模型理解能力，也没有替业务代码取得真实政策。变化是：三步之间的调用和传递，可以交给共同的组合对象安排；调用方提交字典，接收最终文字。

只有这三步时，前面的普通函数很清楚，可以继续使用。后续确实需要频繁组合组件、批量执行或流式输出时，再结合需求选择共同接口，收益才容易观察。

## 新需求先写成普通判断：用户没有填问题怎么办

用户点击提交，但输入框里只有几个空格。正常的产品行为应该是显示“请先填写政策问题”，而不是请求一次模型再等它回复。

这里没有任何需要模型判断的事情。普通Python已经能明确处理：检查类型，清理两端空白，判断剩下的文字是否为空。基础入口使用这个实际函数：

<!-- example-source: examples/20-lcel/basic_demo.py -->

```python
def answer_question(chain, context, question):
    # 普通Python先检查页面输入，不需要模型判断用户有没有输入文字。
    if not isinstance(question, str):
        raise TypeError("question必须是字符串")
    question = question.strip()
    if not question:
        # 提前返回，没有运行chain.invoke，所以不会请求模型。
        return "请先填写政策问题。"
    # 输入有效才执行政策解释；chain负责内部三步的数据交接。
    return chain.invoke({"context": context, "question": question})
```

按一次空问题执行来看：

1. `question.strip()`把几个空格变成空字符串。
2. `if not question`成立。
3. 函数直接返回提示，后面的chain.invoke没有执行。

正常问题则经过同样的检查，再进入已经组装好的解释链。外层的业务判断与内层的模型处理各自负责一段工作，读代码时也可以分别核对。

框架还提供按条件选择路径的`RunnableBranch`，以及把普通函数接入共同接口的`RunnableLambda`。它们适合“希望这段判断或函数本身也参与组合”的情况。**当前需求已经能由上面的if完成，不必为了使用框架，再把它改写成更多组件。**具体的两种写法对照放在[扩展说明](https://github.com/benx92/ai-learning-notes/blob/main/supplements/20-组件组合与运行方式扩展.md)。

## 再有新需求时，一次只增加一件事

文章里出现的其他组件，来自不同需求，并不是这个功能必须继续经过的处理步骤。先不要把它们合成一张需要全部背下来的表。

**如果页面只传“会员标识和问题”，还没有传政策。**程序需要先根据已经确认的业务配置取得条款，再把“条款和问题”交给基础链。这个步骤改变的是输入字段。以后仍要使用会员标识，就在整理时保留它；只需要条款与问题，就只交出这两项。

普通字典取值和赋值就能完成。扩展里的`RunnableParallel`演示怎样把多路处理结果汇总成字典，`RunnablePassthrough.assign`演示怎样保留旧字段并追加新字段。当前本地取值很快，使用并行映射主要是观察字段怎样变化，没有性能上的必要性。

**如果需要同时取得两份互不依赖的资料。**例如一项查询退货条款，另一项查询商品例外说明。两项查询可以同时发起，等资料都到齐再交给模型，这时并行可能节省等待。它不会自动把两份查询变成一次，也不会减少两次查询本来需要完成的工作。这是与“从字典取两个字段”不同的工程需求，本例没有实现远程资料服务。

**如果每天有一批问题要处理。**原来的解释功能不需要重新定义，只是分别运行多份输入。`batch`是这种批量调用的入口，不是把全部问题拼成一个很长的提问。若其中一份输入有问题，如何返回这份错误，要在批量入口明确处理。

**如果界面希望边收到边显示。**原来先等整段回答，再交给页面。现在改成模型交来一小段，程序就交给页面一小段，这种方式叫流式输出，调用入口是`stream`。后续处理如果要等整段收齐，它之后的页面仍然得等。因此扩展里才会比较一次处理完整字符串的函数与逐段处理的生成器；字母大写只是观察机制的实验，不是政策解释本身的功能。

**如果运行环境是异步服务，或者服务出现临时故障。**异步入口`ainvoke`用于让异步程序在等待网络结果时安排其他就绪任务；它不会让模型本身自动生成得更快。超时后再试一次、主服务不可用时返回明确失败提示，则分别属于重试与备用处理。这些都是运行方式或失败处理，不会让模型额外理解政策。

基础功能只需要把一次请求处理正确。这些扩展有各自的触发需求，也应有各自的验证。需要哪一项，就读扩展里的对应部分；无需把它们同时加进这个小功能。

## 先运行基础入口，再核对自己理解的过程

源码集中在[示例目录](https://github.com/benx92/ai-learning-notes/tree/main/examples/20-lcel)。正文的简单入口是[basic_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/basic_demo.py)，复用[chain_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/chain_demo.py)里已有的模板、模型工厂与基础链。无需先读懂后者所有扩展函数。

下载、依赖安装和基础入口命令见正文开头。进入`examples/20-lcel`后运行`basic_demo.py`，可以核对下面的输出。

默认输出为：

```text
离线固定回复只用于观察步骤，不验证模型理解能力。
逐步调用： 教学固定响应：会员订单的申请期限为签收后15日，商品例外仍需核对。
整链调用： 教学固定响应：会员订单的申请期限为签收后15日，商品例外仍需核对。
空问题： 请先填写政策问题。
```

前两种调用得到相同文字，说明同一个固定响应能够走通两条执行路径；空问题直接得到填写提示。固定回复不理解问题，当前验证不代表线上回答效果。

若使用在线模型，在同一个PowerShell会话配置自己的参数，再运行：

```powershell
$env:DEEPSEEK_API_KEY = "填写自己的密钥"
$env:LC_CHAT_MODEL = "填写账户可用的模型名"
.\.venv\Scripts\python.exe basic_demo.py --live
```

在线模式只运行一次生成，不再为逐步与整链对照重复请求。模型客户端读取进程环境变量，不自动加载.env。这里使用已有DeepSeek集成，单次请求超时45秒、客户端重试关闭，具体模型和供应商模式需符合所用服务的支持范围。在线请求使用账户额度，当前没有以真实密钥验证回答效果。

输入整理、字段保留、并行、批量、异步和流式的详细实验，以及重试与回退，见[组件组合与运行方式扩展](https://github.com/benx92/ai-learning-notes/blob/main/supplements/20-组件组合与运行方式扩展.md)。原有实验入口仍保留：

```powershell
.\.venv\Scripts\python.exe chain_demo.py
.\.venv\Scripts\python.exe reliability_demo.py
.\.venv\Scripts\python.exe -m unittest -v
```

读回这段政策解释代码时，先确认四件事：程序已经取得什么资料，模板怎样放入资料和问题，模型调用发生在哪里，最终返回的是整条消息还是回答文字。能对上这四件事，就能判断每个组件在这个需求中承担的工作；后面增加新需求时，再决定让普通Python处理，还是接入共同的组件接口。

## 参考资料

- [LangChain RunnableSequence：顺序组合](https://reference.langchain.com/python/langchain-core/runnables/base/RunnableSequence)
- [StrOutputParser：从响应中取得文本](https://reference.langchain.com/python/langchain-core/output_parsers/string/StrOutputParser)
- [配套运行说明](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/README.md)
