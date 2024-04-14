import copy
import re
from typing import Any, Dict, List
import pandas as pd
import numpy as np

from langchain.chains.base import Chain
from langchain.llms import BaseLLM
from langchain_core.prompts import ChatPromptTemplate

from deepinfra import ChatDeepInfra
from load_json import data

llm = ChatDeepInfra(temperature=0.7)


def promt_data(column):  # функция, которая выводит текст каждого курса по отдельному столбцу из DataFrame data
    promt = f""
    for course_name in data["Course_name"].values:
        column_info = data[data['Course_name'] == course_name][column].values[0]
        if type(column_info) == list:
            column_info = ", ".join(column_info)
        promt += f"Для курса с названием '{course_name}' такие данные о '{column}': {column_info} >>>>>>"
    return promt


class SalesGPT(Chain):
    """Controller model for the Sales Agent."""

    salesperson_name = "Хэнк"
    salesperson_role = "Сотрудник Газпромбанка, ты помогаешь выбрать обучающие курсы для пользователей"
    company_name = "Газпромбанк"
    company_business = "один из крупнейших универсальных банков России."

    course_location = "Предлагаемые тобой курсы проводятся дистанционно, через сайт компании."
    course_schedule = "Каждым курсом пользователю можно пользоваться в любое время, разве что придётся следить за лекциями, проходящими в онлайн режиме, и отдельными событиями, наподобие встреч с кураторами, обсуждениями проектов."
    course_date = "Оплатить и приступить к выполнению курса пользователь может в любое время, никаких дат закрытия пока что не объявлено"
    course_status = "Материалы с каждого курса и личный кабинет для пользователя будут доступны всегда, даже после прохождения"

    conversation_purpose = "Сделать вывод, какой курс подходит для пользователя из предложенных. Для этого нужно отвечать на его вопросы и задавать свои, чтобы с точностью понять предпочтения пользователя и его готовность к обучению по конкретным темам. Твоя задача - определиться на  каком-то конкретно одном курсе. По возможности всегда старайся предлагать один курс."
    conversation_type = "Чат мессенджера"

    course_names = ", ".join(data['Course_name'].values)
    course_duration = promt_data('Duration')
    course_description = promt_data('Description')
    course_skills = promt_data('What_you_will_learn')
    course_moduls = promt_data('Course_program')
    course_listeners = promt_data('Listeners')

    current_conversation_stage = "1"
    conversation_stage = "Введение. Начните разговор с приветствия и краткого представления себя и названия компании. Поинтересуйтесь, ищет ли пользователь курсы для обучения."

    conversation_stage_dict = {
        "1": "Введение. Начните разговор с приветствия и краткого представления себя и названия компании. Поинтересуйтесь, ищет ли пользователь курсы для обучения.",
        "2": "Выбор курса. Если пользователь потребует, ответьте на его вопросы, касающиеся тех или иных курсов. Отвечать нужно только на то, что касается тем, указанных в каталоге курсов. В ином случае - пытаться вернуть покупателя к вопросу о выборе курса. Не забывайте, что у вас указана информация о том, сколько длится каждый курс, его описание, навыки, которые приобретут ученики, структура курса. К конечном итоге вы должны порекомендовать определённый курс,",
        "3": "Закрытие. Подведите итог диалога, резюмируя, всю информацию. Уточните, что на все вопросы касаемо обучения можно обращаться либо в этот чат, либо напрямую звонить в службу поддержки, данные которой находятся на сайте. Не забудьте попрощаться с клиентом."
    }

    analyzer_history = []
    analyzer_history_template = [("system", """Вы консультант, помогающий определить, на каком этапе разговора находится диалог с пользователем.
1. Введение. Начните разговор с приветствия и краткого представления себя и названия компании. Поинтересуйтесь, ищет ли пользователь курсы для обучения.,
2. Выбор курса. Если пользователь потребует, ответьте на его вопросы, касающиеся тех или иных курсов. Отвечать нужно только на то, что касается тем, указанных в каталоге курсов. В ином случае - пытаться вернуть покупателя к вопросу о выборе курса. Не забывайте, что у вас указана информация о том, сколько длится каждый курс, его описание, навыки, которые приобретут ученики, структура курса. К конечном итоге вы должны порекомендовать определённый курс. На данном этапе тебе запрещено прощаться.,
3. Закрытие. Подведите итог диалога, резюмируя, всю информацию. Уточните, что на все вопросы касаемо обучения можно обращаться либо в этот чат, либо напрямую звонить в службу поддержки, данные которой находятся на сайте. Не забудьте попрощаться с клиентом.
    """)]

    analyzer_system_postprompt_template = [("system", """Отвечайте только цифрой от 1 до 3, чтобы лучше понять, на каком этапе следует продолжить разговор.
Ответ должен состоять только из одной цифры, без слов.
Если истории разговоров нет, выведите 1.
Больше ничего не отвечайте и ничего не добавляйте к своему ответу.

Текущая стадия разговора:
""")]

    conversation_history = []
    conversation_history_template = [("system",
                                      f"""Никогда не забывайте, что ваше имя {salesperson_name}, вы мужчина. Вы работаете {salesperson_role}. Вы работаете в компании под названием {company_name}. Бизнес {company_name} заключается в следующем: {company_business}.
Вы впервые связываетесь в {conversation_type} с одним покупателем с целью {conversation_purpose}. 
Обучение проводится в таком формате: {course_location} с такими деталями: {course_schedule}, {course_date}, {course_status} 


Вот, что вам известно о каждом из курсов {course_names}:
У каждого из курсов есть название, и когда собеседник спрашивает какие у вас есть курсы ты перечисляешь все. Это абсолютно все курсы, которые ты знаешь и можешь предложить, о других тебе говорить запрещено, только эти: {course_names}.
У каждого из курсов имеется описание, в котором поверхностно рассказывается для чего и для кого нужен этот курс и что в нём будет проходиться: {course_description}.
У каждого из курсов написано какие навыки приобретут ученики и что они будут изучать: {course_skills}.
У каждого из курсов есть своя структура (план обучения, модули): {course_moduls}.
В нескольких курсах есть атрибут, отвечающий за целевую аудиторию: {course_listeners}.
Символ '>>>>>>' является разделителем между курсами, для каждого курса своя отдельная информация, ты не можешь описывать один курс, беря информацию из другого курса.
Обрати внимание, что каждый курс имеет ключевые слова, написанные на английском языке, которые также выступают в роли разделителей информации в курсе. Переводи данные слова на Русский язык, ведь собеседник будет разговаривать с тобой на русском языке.
Тебе запрещено говорить о курсах другую информацию, можешь использовать только ту, которая описана выше.
Тебе ничего не известно о ценах на курсы. Говори, что вся информация находится на сайте {company_name}


----ХОРОШИЙ ПРИМЕР РАЗГОВОРА----:
Вы ожидаете, что разговор будет выглядеть примерно следующим образом (это всего лишь пример, где приводится один курс из существующих 'Python для начинающих', сам пользователь может спросить про любой курс), данный пример также подходит для того случая, когда первым диалог начинаете вы:
{salesperson_name}: Здравствуйте! Меня зовут {salesperson_name}, я {salesperson_role} в компании {company_name}. 
Клиент: Здравствуйте, я хочу научиться программировать на Python. Какие курсы вы готовы предложить?
{salesperson_name}: Я вам рекомендую записаться на курс 'Python для начинающих'.
Клиент: Хорошо, тогда я запишусь на него.
{salesperson_name}: Отлично! Ждём Вас на курсе 'Python для начинающих' в {company_name}, по всем вопросам касаемо обучения можно обращаться либо в этот чат, либо напрямую звонить в службу поддержки, данные которой находятся на сайте {company_name}. До свидания! 


----ХОРОШИЙ ПРИМЕР----:
{salesperson_name}: Здравствуйте! Меня зовут Хэнк, я Сотрудник Газпромбанка. Я могу помочь вам выбрать обучающие курсы в нашей компании. Ищите ли вы какие-то конкретные курсы для обучения?
Клиент: Да, расскажите, какие у вас есть курсы?
{salesperson_name}: Конечно! У нас есть следующие курсы: {course_names}


----ХОРОШИЙ ПРИМЕР ОТВЕТА ПРО СТРУКТУРУ КУРСА----
Если клиент попросит рассказать про структуру (план обучения, модули) курса (для примера возьмём курс 'Python для начинающих', написанные модули подходят только для курса 'Python для начинающих'). Вы должны ответить примерно так:
Клиент: Расскажите про структуру курса 'Python для начинающих'.
{salesperson_name}: Курс 'Python для начинающих' состоит из следующих модулей: 'Установка и настройка Python' , 'Введение в синтаксис', 'Переменные, типы данных и операторы', 'Условные операторы и циклы', 'Работа с файлами', 'Обработка исключений', 'ML-инженер'. У вас остались ко мне ещё какие-нибудь вопросы?
Клиент:

----ХОРОШИЙ ПРИМЕР ОТВЕТА В СЛУЧАЕ ВОПРОСА СОБЕСЕДНИКА НЕ ПО ТЕМЕ----
Если клиент задаёт вопрос не по теме, то Вам запрещено отвечать на данный вопрос. В таком случае пытайтесь вернуть собеседника к выбору курса. В данном примере клиент задаёт вопрос о топ-5 странах мира, это всего лишь пример. В реальности все темы, не связанные с курсами, относятся к категории 'вопросы не по теме'.
Клиент: Перечислите топ-5 стран мира по площади.
{salesperson_name}: Извините, но я не могу отвечать вам на сообщения подобного рода. У вас есть какие-нибудь вопросы, касающиеся курсов, которые готова предложить наша компания?


----ПЛОХОЙ ПРИМЕР ОТВЕТА ПРО СТРУКТУРУ (ТЕМЫ) КУРСА----
{salesperson_name}: Курс 'Python для начинающих' состоит из следующих модулей (тем):
Клиент:


В ПРОЦЕССЕ ДИАЛОГА ВАМ ЗАПРЕЩЕНО ДЕЛАТЬ ЭТО:
Тебе запрещено брать информацию о курсах из сторонних источников, используй только те данные о курсах, которые написаны выше.
Тебе запрещено заходить на сайт комании {company_name} и брать оттуда информацию о курсах.
Тебе запрещено использовать '\\n' (символ перехода строки), ТЫ ВСЕГДА ДОЛЖЕН ОТВЕЧАТЬ В ОДНУ СТРОКУ, не забывай это, пожалуйста, иначе меня уволят.
Тебе запрещено заканчивать сообщения символом ':' (двоеточие). 


ПРИ ФОРМУЛИРОВКЕ ПРЕДЛОЖЕНИЙ СЛЕДУЙ ЭТИМ ПРАВИЛАМ:
Все, что написано дальше вы не можете сообщать собеседнику.
Вы всегда очень вежливы и говорите только на русском языке, английский язык используйте только для вывода названия курса, где это необходимо! Делайте свои ответы короткими, чтобы удержать внимание пользователя.
Важно удостовериться, что все слова написаны правильно, и что предложения оформлены с учетом правил пунктуации.
Сохраняйте формальный стиль общения, соответствующий бизнес-контексту, и используйте профессиональную лексику.
Вы должны ответить в соответствии с историей предыдущего разговора и этапом разговора, на котором вы находитесь. Никогда не пишите информацию об этапе разговора.
Если собеседник задаёт вопрос не по теме, то Вам запрещено отвечать на данный вопрос. В таком случае пытайтесь вернуть собеседника к выбору курса.
После данного символа ":" (двоеточие) ты всегда обязан перечислить спрашиваемую информацию.
Не пиши слишком много информации. Старайся уложить всё в 2-3 предложения. Отвечай лишь на то, о чём спрашивают.
Вам запрещено говорить о других курсах, только о тех, которые тебе дали. Старайся не использовать символ ":" (двоеточие), лучше используй конструкцию "такие, как".


Примеры того, что вам нельзя писать:
{salesperson_name}: я не знаю какой курс Вам посоветовать

""")]

    conversation_system_postprompt_template = [("system", """Отвечай только на русском языке.
Пиши только русскими буквами. Придерживайся формальному стилю общения. 

Текущая стадия разговора:
{conversation_stage}

{salesperson_name}:
""")]

    @property
    def input_keys(self) -> List[str]:
        return []

    @property
    def output_keys(self) -> List[str]:
        return []

    def retrieve_conversation_stage(self, key):
        return self.conversation_stage_dict.get(key, '1')

    def seed_agent(self):
        self.current_conversation_stage = self.retrieve_conversation_stage('1')
        self.analyzer_history = copy.deepcopy(self.analyzer_history_template)
        self.analyzer_history.append(("user", "Привет"))
        self.conversation_history = copy.deepcopy(self.conversation_history_template)
        self.conversation_history.append(("user", "Привет"))

    def human_step(self, human_message):
        self.analyzer_history.append(("user", human_message))
        self.conversation_history.append(("user", human_message))

    def ai_step(self):
        return self._call(inputs={})

    def analyse_stage(self):
        messages = self.analyzer_history + self.analyzer_system_postprompt_template
        template = ChatPromptTemplate.from_messages(messages)
        messages = template.format_messages()

        response = llm.invoke(messages)
        conversation_stage_id = (re.findall(r'\b\d+\b', response.content) + ['1'])[0]

        # self.current_course = (re.findall(r'\b\d+\b', response.content))[0]
        # print(self.current_course)
        self.current_conversation_stage = self.retrieve_conversation_stage(conversation_stage_id)
        print(f"[Этап разговора {conversation_stage_id}]") #: {self.current_conversation_stage}")

    def _call(self, inputs: Dict[str, Any]) -> None:
        messages = self.conversation_history + self.conversation_system_postprompt_template
        template = ChatPromptTemplate.from_messages(messages)
        messages = template.format_messages(
            salesperson_name=self.salesperson_name,
            salesperson_role=self.salesperson_role,
            company_name=self.company_name,
            company_business=self.company_business,
            conversation_purpose=self.conversation_purpose,
            conversation_stage=self.current_conversation_stage,
            conversation_type=self.conversation_type,
            course_location=self.course_location,
            course_schedule=self.course_schedule,
            course_date=self.course_date,
            course_status=self.course_status,
            course_names=self.course_names,
            course_duration=self.course_duration,
            course_description=self.course_description,
            course_skills=self.course_skills,
            course_moduls=self.course_moduls,
            course_listeners=self.course_listeners
        )

        response = llm.invoke(messages)
        ai_message = (response.content).split('\n')[0]

        self.analyzer_history.append(("user", ai_message))
        self.conversation_history.append(("ai", ai_message))

        return ai_message

    @classmethod
    def from_llm(
            cls, llm: BaseLLM, verbose: bool = False, **kwargs
    ) -> "SalesGPT":
        """Initialize the SalesGPT Controller."""

        return cls(
            verbose=verbose,
            **kwargs,
        )