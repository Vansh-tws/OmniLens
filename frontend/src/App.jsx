import React, { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LineChart, Line, Cell,
} from "recharts";
import "./App.css";

const API = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

const TEXT = {
  en: {
    brand: "OmniLens",
    brandBadge: "Universal",
    brandSubtitle: "Clear answers. Better decisions.",
    tagline: "Make Sense of Your Data. Make Better Decisions.",
    heroSub: "Have a spreadsheet, a pile of records, or information you don't know how to understand? OmniLens helps you discover what's important, understand what it means, and decide what to do next. No technical skills needed.",
    heroBadge: "Universal Data Intelligence Platform",
    exploreMyData: "Explore My Data",
    trySampleBtn: "Try a Sample Dataset",
    reassurance1: "Easy to use",
    reassurance2: "Clear explanations",
    reassurance3: "Insights you can explore",
    navHome: "Home",
    navExplore: "Explore Data",
    navFeatures: "Features",
    navHow: "How It Works",
    navSamples: "Sample Datasets",
    navAbout: "About",
    currentData: "Current Data",
    startExploring: "Start Exploring",
    uploadTitle: "Drop your Excel, CSV, or data file here",
    uploadSub: "Supports CSV, Excel (.xlsx, .xls), JSON, text, HTML and PDF tables.",
    browse: "Choose a file from your computer",
    analyze: "Show me what this file says",
    examples: "Or try an example",
    shop: "Warm Brew Cafe · Sales Data",
    tax: "District Tax Report",
    crime: "Public Safety & Case Records",
    expenses: "Personal Money Ledger",
    privacy: "Your file is not saved to disk by this app. It is processed securely by the OmniLens server and held temporarily in memory for this session.",
    supported: "CSV · Excel · JSON · TXT · HTML · PDF tables",
    working: "Reading your file and uncovering insights…",
    result: "Primary Discovery",
    next: "Recommended Next Steps",
    findings: "What Your Data Is Telling You",
    ask: "Ask a question in everyday language",
    askHint: "For example: Which product brought the most sales? Or why did numbers change?",
    askButton: "Get the answer",
    share: "Share & Export",
    pdf: "Download PDF report",
    word: "Download Word report",
    whatsapp: "Copy WhatsApp summary",
    print: "Print this report",
    clean: "Fix these for me",
    cleanNote: "Preview the changes first. Your original file will never be changed.",
    preview: "Review suggested changes",
    approve: "Approve selected changes and download",
    safe: "Select safe changes",
    before: "Before",
    after: "After",
    evidence: "See source rows",
    downloadRows: "Download these rows (Excel)",
    close: "Close",
    more: "Technical details & data shape",
    compare: "Compare two files",
    compareHelp: "Choose two versions. OmniLens will match common fields automatically.",
    compareSamples: "Try the ready-made shop comparison pair:",
    compareEarlier: "Download earlier period",
    compareLater: "Download later period",
    compareRun: "Compare files",
    read: "Read this to me",
    large: "A+",
    contrast: "HC",
    language: "Language",
    noAnswer: "I could not safely answer that from this file.",
    limit: "What this file cannot tell us",
    examplesTitle: "See What OmniLens Can Discover",
    sampleSub: "Explore real-world examples with instant plain-English discoveries and interactive charts.",
    trySample: "Explore This Dataset",
    government: "Government & Public Services",
    governmentDesc: "District reports, public-service records, and administrative totals.",
    business: "Business & Retail",
    businessDesc: "Coffee shop sales, product margins, and customer order patterns.",
    personal: "Personal Finance",
    personalDesc: "Understand everyday income, spending categories, and money movement.",
    taxDesc: "Taxpayer groups, income bands, totals and weighted averages.",
    crimeDesc: "Incident records, case follow-ups, and resolution timelines.",
    shopDesc: "Six months of coffee, snacks, revenue, costs, and busy day trends.",
    expensesDesc: "Six months of income received, household expenses, and payment methods.",
    shareDesc: "Create a formal PDF report, copy a WhatsApp summary, or print your results.",
    cleanDesc: "Review suggested fixes and download a cleaned Excel copy. Original remains untouched.",
    compareDesc: "Compare two periods of sales or data. OmniLens finds common measures automatically.",
    showOptions: "Choose export option",
    uploadAgain: "Choose another file",
    loading: "Finding the answer…",
    errors: "I couldn’t read this file.",
    selectF: "Choose first file",
    selectS: "Choose second file",
    technical: "Technical details (optional)",
    imported: "Rows of information",
    charts: "Interactive Visualisations",
    empty: "No clear finding is ready yet. Try asking a question or check the file’s column names.",
    completed: "Done",
    approveFuzzy: "Approve this spelling match",
    allSafe: "Select all safe changes",
    noChanges: "No suggested changes were found.",
    actionsEmpty: "No urgent action was identified. Check the source period and field meanings.",
    whatsappCopied: "Summary copied! Paste it into WhatsApp.",
    processingError: "Please try an Excel or CSV copy, or check that the file has column headings.",
    chooseFirst: "Choose a file first.",
    noCompare: "Choose both files to compare.",
    rowQuestion: "How is this data organized?",
    person: "Each row is one person or transaction",
    group: "Each row is a group or summary",
    time: "Measurements taken over time",
    contact: "A list of names or contacts",
    textRows: "Written comments or notes",
    placeRows: "Area or district summary",
    notSure: "Not sure / let OmniLens decide",
    continue: "Continue with this structure",
  },
  hi: {
    brand: "ओमनीलेंस",
    brandBadge: "यूनिवर्सल",
    brandSubtitle: "स्पष्ट जवाब। बेहतर फैसले।",
    tagline: "डेटा को समझें। बेहतर निर्णय लें।",
    heroSub: "क्या आपके पास स्प्रेडशीट या रिकॉर्ड हैं जिन्हें समझना मुश्किल है? OmniLens महत्वपूर्ण जानकारी खोजने, उसका अर्थ समझाने और आगे क्या करना है यह तय करने में मदद करता है। किसी तकनीकी ज्ञान की आवश्यकता नहीं।",
    heroBadge: "यूनिवर्सल डेटा इंटेलिजेंस प्लेटफॉर्म",
    exploreMyData: "मेरा डेटा देखें",
    trySampleBtn: "उदाहरण डेटा आज़माएँ",
    reassurance1: "इस्तेमाल में आसान",
    reassurance2: "स्पष्ट व्याख्या",
    reassurance3: "खोजने योग्य निष्कर्ष",
    navHome: "होम",
    navExplore: "डेटा देखें",
    navFeatures: "विशेषताएँ",
    navHow: "कैसे काम करता है",
    navSamples: "उदाहरण डेटा",
    navAbout: "हमारे बारे में",
    currentData: "मौजूदा डेटा",
    startExploring: "शुरू करें",
    uploadTitle: "अपनी Excel या CSV फ़ाइल यहाँ डालें",
    uploadSub: "CSV, Excel (.xlsx, .xls), JSON, टेक्स्ट, HTML या PDF टेबल भी चुन सकते हैं।",
    browse: "फ़ाइल चुनें",
    analyze: "फ़ाइल में क्या है, बताएं",
    examples: "या उदाहरण आज़माएँ",
    shop: "दुकान की बिक्री · 6 माह",
    tax: "जिला कर रिपोर्ट",
    crime: "अपराध आँकड़े",
    expenses: "व्यक्तिगत लेन-देन",
    privacy: "यह ऐप आपकी फ़ाइल को डिस्क पर सेव नहीं करता। यह सुरक्षित रूप से प्रोसेस होकर मेमोरी में ही रहती है।",
    supported: "CSV · Excel · JSON · TXT · HTML · PDF टेबल",
    working: "फ़ाइल पढ़ी जा रही है…",
    result: "मुख्य निष्कर्ष",
    next: "अनुशंसित अगले कदम",
    findings: "ध्यान देने योग्य बातें",
    ask: "अपनी भाषा में सवाल पूछें",
    askHint: "उदाहरण: किस उत्पाद से सबसे ज़्यादा बिक्री हुई?",
    askButton: "जवाब देखें",
    share: "शेयर और डाउनलोड",
    pdf: "PDF रिपोर्ट डाउनलोड करें",
    word: "Word रिपोर्ट डाउनलोड करें",
    whatsapp: "WhatsApp सारांश कॉपी करें",
    print: "प्रिंट करें",
    clean: "फ़ाइल ठीक करने में मदद करें",
    cleanNote: "पहले बदलाव देखें। आपकी मूल फ़ाइल नहीं बदलेगी।",
    preview: "बदलाव देखें",
    approve: "चुने हुए बदलाव स्वीकार कर डाउनलोड करें",
    safe: "सुरक्षित बदलाव चुनें",
    before: "पहले",
    after: "बाद में",
    evidence: "स्रोत पंक्तियाँ देखें",
    downloadRows: "ये पंक्तियाँ Excel में डाउनलोड करें",
    close: "बंद करें",
    more: "तकनीकी विवरण",
    compare: "दो फ़ाइलों की तुलना करें",
    compareHelp: "दो संस्करण चुनें। समान फ़ील्ड अपने-आप मिलाए जाएंगे।",
    compareSamples: "तैयार दुकान तुलना फ़ाइलें आज़माएँ:",
    compareEarlier: "पहली अवधि डाउनलोड करें",
    compareLater: "बाद की अवधि डाउनलोड करें",
    compareRun: "तुलना करें",
    read: "मुझे पढ़कर सुनाएँ",
    large: "A+",
    contrast: "HC",
    language: "भाषा",
    noAnswer: "इस फ़ाइल से सुरक्षित रूप से जवाब नहीं मिल पाया।",
    limit: "यह फ़ाइल क्या नहीं बता सकती",
    examplesTitle: "देखें OmniLens क्या खोज सकता है",
    sampleSub: "काल्पनिक वास्तविक डेटा उदाहरणों के साथ तुरंत निष्कर्ष देखें।",
    trySample: "उदाहरण देखें",
    government: "सरकार और सार्वजनिक सेवाएँ",
    governmentDesc: "जिला रिपोर्ट और सार्वजनिक सेवा रिकॉर्ड।",
    business: "व्यवसाय",
    businessDesc: "दुकान की बिक्री और व्यवसाय का प्रदर्शन।",
    personal: "व्यक्तिगत वित्त",
    personalDesc: "रोज़मर्रा के पैसों के लेन-देन को समझें।",
    taxDesc: "करदाता समूह, आय वर्ग, कुल और भारित औसत।",
    crimeDesc: "काल्पनिक घटना रिकॉर्ड, जिले और मामलों की स्थिति।",
    shopDesc: "छह महीने के उत्पाद, बिक्री, लागत और ग्राहक।",
    expensesDesc: "छह महीने की प्राप्तियाँ, खर्च और भुगतान की स्थिति।",
    shareDesc: "रिपोर्ट बनाएँ, WhatsApp सारांश कॉपी करें या प्रिंट करें।",
    cleanDesc: "सुझाए गए बदलाव देखें और साफ़ कॉपी डाउनलोड करें।",
    compareDesc: "दो फ़ाइल संस्करणों की तुलना करें।",
    showOptions: "शेयर करने का तरीका चुनें",
    uploadAgain: "दूसरी फ़ाइल चुनें",
    loading: "कृपया रुकें…",
    errors: "यह फ़ाइल पढ़ी नहीं जा सकी।",
    selectF: "पहली फ़ाइल चुनें",
    selectS: "दूसरी फ़ाइल चुनें",
    technical: "तकनीकी जानकारी (ज़रूरत होने पर)",
    imported: "जानकारी की पंक्तियाँ",
    charts: "उपयोगी चार्ट",
    empty: "अभी स्पष्ट जानकारी नहीं मिली। सवाल पूछें या कॉलम के नाम जाँचें।",
    completed: "पूरा हुआ",
    approveFuzzy: "इस नाम के बदलाव को स्वीकार करें",
    allSafe: "सभी सुरक्षित बदलाव चुनें",
    noChanges: "कोई बदलाव सुझाया नहीं गया।",
    actionsEmpty: "कोई ज़रूरी कदम नहीं मिला।",
    whatsappCopied: "सारांश कॉपी हुआ। WhatsApp में पेस्ट करें।",
    processingError: "Excel या CSV फ़ाइल आज़माएँ या कॉलम हेडिंग जाँचें।",
    chooseFirst: "पहले फ़ाइल चुनें।",
    noCompare: "तुलना के लिए दोनों फ़ाइलें चुनें।",
    rowQuestion: "यह डेटा कैसे व्यवस्थित है?",
    person: "प्रत्येक पंक्ति एक व्यक्ति या लेन-देन है",
    group: "प्रत्येक पंक्ति एक समूह या सारांश है",
    time: "समय के साथ लिए गए माप",
    contact: "नामों या संपर्कों की सूची",
    textRows: "लिखित टिप्पणियाँ या नोट्स",
    placeRows: "क्षेत्र या जिला सारांश",
    notSure: "निश्चित नहीं",
    continue: "आगे बढ़ें",
  },
  mr: {
    brand: "ओम्नीलेंस",
    brandBadge: "युनिव्हर्सल",
    brandSubtitle: "स्पष्ट उत्तरे. उत्तम निर्णय.",
    tagline: "डेटा समजून घ्या. अधिक योग्य निर्णय घ्या.",
    heroSub: "स्प्रेडशीट किंवा रेकॉर्ड्स समजणे कठीण वाटते का? OmniLens महत्त्वाची माहिती शोधण्यात, तिचा अर्थ समजावून घेण्यात आणि पुढील दिशा ठरवण्यात मदत करतो. तांत्रिक ज्ञानाची गरज नाही.",
    heroBadge: "युनिव्हर्सल डेटा इंटेलिजन्स प्लॅटफॉर्म",
    exploreMyData: "माझा डेटा तपासा",
    trySampleBtn: "नमुना डेटा वापरा",
    reassurance1: "वापरण्यास सोपे",
    reassurance2: "स्पष्ट स्पष्टीकरण",
    reassurance3: "तपासण्यासारखे निष्कर्ष",
    navHome: "मुख्यपृष्ठ",
    navExplore: "डेटा तपासा",
    navFeatures: "वैशिष्ट्ये",
    navHow: "कसे चालते",
    navSamples: "नमुना डेटा",
    navAbout: "आमच्याबद्दल",
    currentData: "सध्याचा डेटा",
    startExploring: "सुरू करा",
    uploadTitle: "तुमची Excel किंवा CSV फाइल इथे टाका",
    uploadSub: "CSV, Excel, JSON, मजकूर, HTML किंवा टेबल असलेली PDF देखील निवडू शकता.",
    browse: "फाइल निवडा",
    analyze: "फाइलमध्ये काय आहे ते सांगा",
    examples: "किंवा उदाहरण वापरा",
    shop: "दुकानाची विक्री · ६ महिने",
    tax: "जिल्हानिहाय कर अहवाल",
    crime: "गुन्हेगारी आकडेवारी",
    expenses: "वैयक्तिक व्यवहार",
    privacy: "हे अॅप तुमची फाइल डिस्कवर सेव्ह करत नाही. ती फक्त तात्पुरती मेमरीमध्ये सुरक्षित राहते.",
    supported: "CSV · Excel · JSON · TXT · HTML · PDF टेबल",
    working: "फाइल वाचत आहे…",
    result: "मुख्य शोध",
    next: "पुढील उपयुक्त पावले",
    findings: "तपासण्यासारख्या गोष्टी",
    ask: "तुमच्या शब्दांत प्रश्न विचारा",
    askHint: "उदाहरण: कोणत्या उत्पादनाची विक्री सर्वाधिक झाली?",
    askButton: "उत्तर पहा",
    share: "शेअर व डाऊनलोड",
    pdf: "PDF अहवाल डाउनलोड करा",
    word: "Word अहवाल डाउनलोड करा",
    whatsapp: "WhatsApp सारांश कॉपी करा",
    print: "प्रिंट करा",
    clean: "फाइल दुरुस्त करण्यात मदत करा",
    cleanNote: "आधी बदल पहा. मूळ फाइल बदलली जाणार नाही.",
    preview: "सुचवलेले बदल पहा",
    approve: "बदल मंजूर करून डाउनलोड करा",
    safe: "सुरक्षित बदल निवडा",
    before: "आधी",
    after: "नंतर",
    evidence: "स्रोत ओळी पहा",
    downloadRows: "या ओळी Excel मध्ये डाउनलोड करा",
    close: "बंद करा",
    more: "तांत्रिक माहिती",
    compare: "दोन फाइल्सची तुलना करा",
    compareHelp: "दोन आवृत्त्या निवडा. समान फील्ड आपोआप जुळवली जातील.",
    compareSamples: "तयार दुकान तुलना फाइल्स वापरून पहा:",
    compareEarlier: "आधीचा कालावधी डाउनलोड करा",
    compareLater: "नंतरचा कालावधी डाउनलोड करा",
    compareRun: "तुलना करा",
    read: "मला वाचून दाखवा",
    large: "A+",
    contrast: "HC",
    language: "भाषा",
    noAnswer: "या फाइलमधून सुरक्षितपणे उत्तर देता आले नाही.",
    limit: "ही फाइल काय सांगू शकत नाही",
    examplesTitle: "OmniLens काय शोधू शकते ते पहा",
    sampleSub: "काल्पनिक माहितीवर आधारित वास्तविक नमुने तपासा.",
    trySample: "नमुना पहा",
    government: "सरकार आणि सार्वजनिक सेवा",
    governmentDesc: "जिल्हा अहवाल आणि सार्वजनिक सेवा नोंदी.",
    business: "व्यवसाय",
    businessDesc: "दुकानाची विक्री आणि व्यवसायाची कामगिरी.",
    personal: "वैयक्तिक वित्त",
    personalDesc: "दैनंदिन पैशांचे व्यवहार समजून घ्या.",
    taxDesc: "करदाता गट, उत्पन्न श्रेणी, एकूण आणि भारित सरासरी.",
    crimeDesc: "काल्पनिक घटना नोंदी, जिल्हे आणि प्रकरणांची स्थिती.",
    shopDesc: "सहा महिन्यांचे उत्पादने, विक्री, खर्च आणि ग्राहक.",
    expensesDesc: "सहा महिन्यांचे जमा, खर्च आणि पेमेंट स्थिती.",
    shareDesc: "अहवाल तयार करा, WhatsApp सारांश कॉपी करा किंवा प्रिंट करा.",
    cleanDesc: "सुचवलेले बदल तपासा आणि स्वच्छ प्रत डाउनलोड करा.",
    compareDesc: "दोन फाइल आवृत्त्यांची तुलना करा.",
    showOptions: "शेअर करण्याचा पर्याय निवडा",
    uploadAgain: "दुसरी फाइल निवडा",
    loading: "कृपया थांबा…",
    errors: "ही फाइल वाचता आली नाही.",
    selectF: "पहिली फाइल निवडा",
    selectS: "दुसरी फाइल निवडा",
    technical: "तांत्रिक माहिती (ऐच्छिक)",
    imported: "नोंदींच्या ओळी",
    charts: "उपयुक्त चार्ट",
    empty: "अद्याप स्पष्ट निष्कर्ष मिळाला नाही. प्रश्न विचारा किंवा कॉलमची नावे तपासा.",
    completed: "पूर्ण झाले",
    approveFuzzy: "हे स्पेलिंग बदल मंजूर करा",
    allSafe: "सर्व सुरक्षित बदल निवडा",
    noChanges: "कोणतेही बदल सुचवलेले नाहीत.",
    actionsEmpty: "तातडीची कृती आढळली नाही.",
    whatsappCopied: "सारांश कॉपी झाला. WhatsApp मध्ये पेस्ट करा.",
    processingError: "Excel किंवा CSV फाइल वापरून पहा किंवा कॉलम हेडिंग तपासा.",
    chooseFirst: "आधी फाइल निवडा.",
    noCompare: "तुलनेसाठी दोन्ही फाइल्स निवडा.",
    rowQuestion: "ही माहिती कशी मांडली आहे?",
    person: "प्रत्येक ओळ एक व्यक्ती किंवा व्यवहार आहे",
    group: "प्रत्येक ओळ एक गट किंवा सारांश आहे",
    time: "काळाच्या ओघात घेतलेली मोजमापे",
    contact: "नावे किंवा संपर्कांची यादी",
    textRows: "नोंदी किंवा प्रतिक्रिया",
    placeRows: "भाग किंवा जिल्हा सारांश",
    notSure: "नक्की नाही",
    continue: "पुढे जा",
  },
};

// Demo sample weekend sales data for the interactive Hero Preview Card
const HERO_WEEKEND_TREND = [
  { day: "Mon", sales: 12400, isWeekend: false },
  { day: "Tue", sales: 14200, isWeekend: false },
  { day: "Wed", sales: 13800, isWeekend: false },
  { day: "Thu", sales: 15600, isWeekend: false },
  { day: "Fri", sales: 21800, isWeekend: false },
  { day: "Sat", sales: 28400, isWeekend: true },
  { day: "Sun", sales: 26900, isWeekend: true },
];

function App() {
  const [lang, setLang] = useState("en");
  const t = TEXT[lang] || TEXT.en;

  // Analysis & Session State
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [sessionId, setSessionId] = useState("");
  const [dashTab, setDashTab] = useState("overview");

  // Hero Card Interactive Preview state
  const [heroPreviewTab, setHeroPreviewTab] = useState("finding");
  const [previewChatAnswer, setPreviewChatAnswer] = useState({
    q: "Which product generated the highest margin?",
    a: "Caramel Macchiato generated a 78% gross margin, contributing ₹18,400 in profit. Top weekend performer.",
    method: "Calculated by comparing unit prices with inventory costs across 84 sales transactions.",
  });

  // Natural language Q&A state
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);

  // Evidence modal state
  const [evidence, setEvidence] = useState(null);
  const [evidenceFinding, setEvidenceFinding] = useState(null);

  // Data Cleaning state
  const [cleanOpen, setCleanOpen] = useState(false);
  const [clean, setClean] = useState(null);
  const [cleanPreview, setCleanPreview] = useState(null);
  const [cleanPreviewLoading, setCleanPreviewLoading] = useState(false);
  const [cleanSelected, setCleanSelected] = useState([]);
  const [spellMappings, setSpellMappings] = useState({});

  // File Compare state
  const [compareA, setCompareA] = useState(null);
  const [compareB, setCompareB] = useState(null);
  const [compareResult, setCompareResult] = useState(null);

  // Usability & Accessibility state
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [largeText, setLargeText] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [doneActions, setDoneActions] = useState({});
  const [rowMeaning, setRowMeaning] = useState("not_sure");
  const [dragActive, setDragActive] = useState(false);

  // Privacy, Zero-Retention & Security state
  const [sessionTimeLeft, setSessionTimeLeft] = useState(1800);
  const [privacyModalOpen, setPrivacyModalOpen] = useState(false);
  const [privacyAuditData, setPrivacyAuditData] = useState(null);
  const [burnToast, setBurnToast] = useState("");

  // Voice Q&A state
  const [isListening, setIsListening] = useState(false);

  const session = result?.session_id || sessionId;
  const analysis = result?.analysis;
  const suggested = result?.suggested_questions || [];

  async function requestJson(url, options = {}) {
    const response = await fetch(`${API}${url}`, options);
    const type = response.headers.get("content-type") || "";
    if (!response.ok) {
      let message = "Something went wrong. Please try again.";
      try {
        const body = type.includes("json") ? await response.json() : await response.text();
        message = body.detail || body || message;
      } catch {
        /* ignore */
      }
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    return type.includes("json") ? response.json() : response.blob();
  }

  async function analyzeFile(selectedFile) {
    if (!selectedFile) {
      setError(t.chooseFirst);
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    setSessionId("");
    setAnswer(null);
    setCompareResult(null);
    setFile(selectedFile);
    try {
      const form = new FormData();
      form.append("file", selectedFile);
      const data = await requestJson(`/api/analyze?language=${lang}`, { method: "POST", body: form });
      setResult(data);
      setSessionId(data.session_id);
      setQuestion("");
      setDoneActions({});
      setRowMeaning("not_sure");
      setDashTab("overview");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e.message || t.processingError);
    } finally {
      setBusy(false);
    }
  }

  async function loadSample(id) {
    setBusy(true);
    setError("");
    setResult(null);
    setAnswer(null);
    setFile(null);
    setSessionId("");
    try {
      const data = await requestJson(`/api/sample/${id}?language=${lang}`, { method: "POST" });
      setResult(data);
      setSessionId(data.session_id);
      setDoneActions({});
      setDashTab("overview");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function askQuestion(text = question) {
    const q = (text || "").trim();
    if (!q || !session) return;
    setAsking(true);
    setAnswer(null);
    try {
      const data = await requestJson("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session, question: q }),
      });
      setAnswer(data);
      setQuestion(q);
    } catch (e) {
      setError(e.message);
    } finally {
      setAsking(false);
    }
  }

  async function showEvidence(finding) {
    setEvidenceFinding(finding);
    setEvidence(null);
    try {
      const res = await requestJson(`/api/evidence/${session}/${finding.id}`);
      setEvidence(res);
    } catch (e) {
      setError(e.message);
    }
  }

  async function openCleaning() {
    setCleanOpen(true);
    setClean(null);
    setCleanPreview(null);
    setCleanSelected([]);
    setSpellMappings({});
    try {
      const res = await requestJson(`/api/clean/preview/${session}`);
      setClean(res);
    } catch (e) {
      setError(e.message);
      setCleanOpen(false);
    }
  }

  function chooseSafeChanges() {
    const safe = (clean?.changes || []).filter((x) => x.safe).map((x) => x.id);
    setCleanSelected(safe);
  }

  function toggleClean(id) {
    setCleanSelected((old) => (old.includes(id) ? old.filter((x) => x !== id) : [...old, id]));
  }

  async function applyCleaning() {
    try {
      const mappings = {};
      (clean?.changes || [])
        .filter((x) => x.id === "normalise_spelling")
        .forEach((change) => {
          (change.suggestions || []).forEach((s, i) => {
            if (spellMappings[`${s.field}-${i}`]) {
              s.variants.forEach((v) => {
                if (v !== s.suggested_value) mappings[`${s.field}::${v}`] = s.suggested_value;
              });
            }
          });
        });
      const approved = [...cleanSelected];
      if (Object.values(spellMappings).some(Boolean) && !approved.includes("normalise_spelling")) {
        approved.push("normalise_spelling");
      }
      const response = await fetch(`${API}/api/clean/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session, approved, fuzzy_mappings: mappings, output_format: "xlsx" }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Could not prepare the cleaned file.");
      }
      downloadBlob(await response.blob(), "OmniLens_cleaned.xlsx");
      setCleanOpen(false);
    } catch (e) {
      setError(e.message);
    }
  }

  async function downloadReport(format) {
    try {
      const blob = await requestJson(`/api/report/${session}?format=${format}`);
      downloadBlob(blob, format === "pdf" ? "OmniLens_report.pdf" : "OmniLens_report.docx");
    } catch (e) {
      setError(e.message);
    }
  }

  async function copyWhatsApp() {
    try {
      const data = await requestJson(`/api/share-text/${session}`);
      await navigator.clipboard.writeText(data.text);
      window.alert(t.whatsappCopied);
    } catch (e) {
      setError(e.message);
    }
  }

  async function compareFiles() {
    if (!compareA || !compareB) {
      setError(t.noCompare);
      return;
    }
    setBusy(true);
    setCompareResult(null);
    setError("");
    try {
      const form = new FormData();
      form.append("file_a", compareA);
      form.append("file_b", compareB);
      const data = await requestJson("/api/compare", { method: "POST", body: form });
      setCompareResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmRows() {
    if (!session || !rowMeaning) return;
    try {
      const data = await requestJson("/api/confirm-rows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session, row_meaning: rowMeaning }),
      });
      setResult((old) => (old ? { ...old, analysis: data.analysis } : old));
    } catch (e) {
      setError(e.message);
    }
  }

  function speak(text) {
    if (!("speechSynthesis" in window)) {
      setError("Read aloud is not supported by this browser.");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === "hi" ? "hi-IN" : lang === "mr" ? "mr-IN" : "en-IN";
    window.speechSynthesis.speak(utterance);
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function changeFile() {
    if (session) {
      fetch(`${API}/api/session/${session}/purge`, { method: "POST" }).catch(() => {});
    }
    setResult(null);
    setSessionId("");
    setFile(null);
    setAnswer(null);
    setError("");
    setClean(null);
    setEvidence(null);
    setCompareResult(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function scrollToSection(id) {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  }

  // Handle Drag & Drop
  function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }
  function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }
  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  }

  // Live Clean Preview Effect
  useEffect(() => {
    if (!cleanOpen || !clean || !session) return;
    let cancelled = false;
    const mappings = {};
    (clean.changes || [])
      .filter((change) => change.id === "normalise_spelling")
      .forEach((change) => {
        (change.suggestions || []).forEach((suggestion, index) => {
          if (spellMappings[`${suggestion.field}-${index}`]) {
            suggestion.variants.forEach((value) => {
              if (value !== suggestion.suggested_value) mappings[`${suggestion.field}::${value}`] = suggestion.suggested_value;
            });
          }
        });
      });
    const approved = [...cleanSelected];
    if (Object.keys(mappings).length && !approved.includes("normalise_spelling")) approved.push("normalise_spelling");

    setCleanPreviewLoading(true);
    fetch(`${API}/api/clean/preview-approved`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: session, approved, fuzzy_mappings: mappings }),
    })
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || "Could not update the preview.");
        return body;
      })
      .then((data) => {
        if (!cancelled) setCleanPreview(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setCleanPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cleanOpen, clean, cleanSelected, spellMappings, session]);

  // Zero-Retention Burn Handler
  async function burnSession(autoExpired = false) {
    if (session) {
      try {
        await fetch(`${API}/api/session/${session}/purge`, { method: "POST" });
      } catch {
        try {
          await fetch(`${API}/api/session/${session}`, { method: "DELETE" });
        } catch {
          /* ignore */
        }
      }
    }
    setResult(null);
    setSessionId("");
    setFile(null);
    setAnswer(null);
    setError("");
    setClean(null);
    setEvidence(null);
    setCompareResult(null);
    setDoneActions({});
    setQuestion("");
    setBurnToast(
      autoExpired
        ? "⏰ Session expired — all dataset records automatically erased from memory."
        : "🔥 Zero-Retention Burn Executed: Dataset wiped from server RAM & session terminated."
    );
    setTimeout(() => setBurnToast(""), 7000);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // Load server privacy audit facts
  async function loadPrivacyAudit() {
    try {
      const res = await fetch(`${API}/api/privacy-audit`);
      if (res.ok) {
        const data = await res.json();
        setPrivacyAuditData(data);
      }
    } catch {
      /* fallback */
    }
  }

  // Session countdown timer effect
  useEffect(() => {
    if (!session) return;
    setSessionTimeLeft(1800);
    const interval = setInterval(() => {
      setSessionTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          burnSession(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [session]);

  // Tab unload auto-destruct (beacon purge)
  useEffect(() => {
    const handleUnload = () => {
      if (session) {
        try {
          navigator.sendBeacon(`${API}/api/session/${session}/purge`);
        } catch {
          /* ignore */
        }
      }
    };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, [session]);

  // Voice Q&A toggle
  function toggleVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice input is supported in Google Chrome, Microsoft Edge, and Safari.");
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      
      if (lang === "hi") recognition.lang = "hi-IN";
      else if (lang === "mr") recognition.lang = "mr-IN";
      else recognition.lang = "en-IN";

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          setQuestion(transcript);
        }
        setIsListening(false);
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
    } catch (err) {
      setIsListening(false);
    }
  }

  const cleanBeforeRows = clean?.before || [];
  const cleanAfterRows = cleanPreview?.after ?? clean?.after_safe ?? cleanBeforeRows;
  const appClass = `app-shell${largeText ? " large-text" : ""}${highContrast ? " high-contrast" : ""}`;

  return (
    <div className={appClass}>
      {/* ====================================================================
          TOP NAVIGATION BAR (Exact Match to User Reference Image)
          ==================================================================== */}
      <header className="topbar-wrap">
        <div className="topbar">
          <div className="brand-link" onClick={() => (result ? setDashTab("overview") : window.scrollTo({ top: 0, behavior: "smooth" }))}>
            {/* Custom Starbucks-inspired Leaf / Lens Brand Emblem */}
            <div className="brand-logo-badge" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="white" strokeWidth="1.6" strokeOpacity="0.4" />
                <path d="M12 4C12 4 17 8 17 12C17 14.7614 14.7614 17 12 17C9.23858 17 7 14.7614 7 12C7 8 12 4 12 4Z" fill="white" />
                <circle cx="12" cy="12" r="2.5" fill="#006241" />
              </svg>
            </div>
            <div className="brand-text">
              <div className="brand-title-row">
                <span className="brand-name">{t.brand}</span>
                <span className={`brand-tag ${result ? "has-data" : ""}`}>{t.brandBadge}</span>
              </div>
              <span className="brand-subtitle">{t.brandSubtitle}</span>
            </div>
          </div>

          <nav className="nav-links" aria-label="Main Navigation">
            <span className={`nav-item ${!result ? "active" : ""}`} onClick={() => { if (result) setResult(null); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
              {t.navHome}
            </span>
            <span className="nav-item" onClick={() => (result ? setDashTab("explore") : scrollToSection("upload-section"))}>
              {t.navExplore}
            </span>
            <span className="nav-item" onClick={() => scrollToSection("features-section")}>
              {t.navFeatures}
            </span>
            <span className="nav-item" onClick={() => scrollToSection("how-it-works-section")}>
              {t.navHow}
            </span>
            <span className="nav-item" onClick={() => scrollToSection("samples-section")}>
              {t.navSamples}
            </span>
            <span className="nav-item" onClick={() => scrollToSection("about-section")}>
              {t.navAbout}
            </span>
          </nav>

          <div className="nav-actions">
            {result ? (
              <button className="current-data-btn" onClick={() => setDashTab("overview")} title="View Current Active Dataset">
                <span>🗄 {t.currentData}: {result.filename.length > 18 ? result.filename.slice(0, 15) + "…" : result.filename}</span>
                <span className="btn-arrow">→</span>
              </button>
            ) : (
              <button className="explore-nav-btn" onClick={() => scrollToSection("upload-section")}>
                <span>{t.startExploring}</span>
                <span>→</span>
              </button>
            )}

            <div className="nav-controls">
              <div className="lang-select-wrap">
                <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label={t.language}>
                  <option value="en">English</option>
                  <option value="hi">हिन्दी</option>
                  <option value="mr">मराठी</option>
                </select>
              </div>
              <button className={`btn-icon-square ${largeText ? "active" : ""}`} onClick={() => setLargeText((x) => !x)} title="Larger Text size">
                A+
              </button>
              <button className={`btn-icon-square ${highContrast ? "active" : ""}`} onClick={() => setHighContrast((x) => !x)} title="High Contrast mode">
                HC
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Zero-Retention Burn Notification Toast */}
      {burnToast && (
        <div className="burn-toast-banner" role="alert">
          <div className="burn-toast-content">
            <span className="burn-toast-icon">🛡️</span>
            <span>{burnToast}</span>
          </div>
          <button className="burn-toast-close" onClick={() => setBurnToast("")} aria-label="Dismiss">✕</button>
        </div>
      )}

      {/* ====================================================================
          LANDING PAGE HERO SECTION (When no dataset active, or top banner)
          Exact match to Reference Photo
          ==================================================================== */}
      {!result && (
        <>
          <section className="hero-section" id="hero-section">
            <div className="hero-container">
              {/* Left Column: Headline, Description & CTAs */}
              <div className="hero-content">
                <div className="hero-pill-badge">
                  <span className="sparkle">✦</span>
                  <span>{t.heroBadge}</span>
                </div>

                <h1 className="hero-title">
                  Make Sense of Your Data.<br />
                  <span className="title-accent">Make Better Decisions.</span>
                </h1>

                <p className="hero-description">
                  Have a spreadsheet, a pile of records, or information you don't know how to understand? OmniLens helps you discover what's important, understand what it means, and decide what to do next. <strong>No technical skills needed.</strong>
                </p>

                <div className="hero-cta-group">
                  <button className="primary-btn" onClick={() => scrollToSection("upload-section")}>
                    <span>{t.exploreMyData}</span>
                    <span className="btn-arrow">→</span>
                  </button>
                  <button className="secondary-btn" onClick={() => scrollToSection("samples-section")}>
                    <span>{t.trySampleBtn}</span>
                  </button>
                </div>

                <div className="hero-reassurance-row">
                  <div className="reassurance-item">
                    <span className="reassurance-bullet" />
                    <span>{t.reassurance1}</span>
                  </div>
                  <div className="reassurance-item">
                    <span className="reassurance-bullet" />
                    <span>{t.reassurance2}</span>
                  </div>
                  <div className="reassurance-item">
                    <span className="reassurance-bullet" />
                    <span>{t.reassurance3}</span>
                  </div>
                </div>
              </div>

              {/* Right Column: Hero Preview Card (Matches Photo Reference) */}
              <div className="hero-visual-card">
                <div className="preview-card-header">
                  <div>
                    <div className="preview-subheading">SAMPLE DATASET PREVIEW</div>
                    <div className="preview-title-row">
                      <span className="live-indicator-dot" />
                      <span className="preview-dataset-title">Warm Brew Cafe — Sales Data</span>
                    </div>
                  </div>
                  <span className="preview-badge-pill">84 records analyzed</span>
                </div>

                {/* Segmented Pills */}
                <div className="preview-segmented-tabs">
                  <button
                    className={`preview-tab-btn ${heroPreviewTab === "finding" ? "active" : ""}`}
                    onClick={() => setHeroPreviewTab("finding")}
                  >
                    Key Finding
                  </button>
                  <button
                    className={`preview-tab-btn ${heroPreviewTab === "ask" ? "active" : ""}`}
                    onClick={() => setHeroPreviewTab("ask")}
                  >
                    Ask OmniLens
                  </button>
                  <button
                    className={`preview-tab-btn ${heroPreviewTab === "trend" ? "active" : ""}`}
                    onClick={() => setHeroPreviewTab("trend")}
                  >
                    Quick Trend
                  </button>
                </div>

                {/* Tab 1: Key Finding Content */}
                {heroPreviewTab === "finding" && (
                  <>
                    <div className="observed-discovery-card">
                      <div className="subcard-top-row">
                        <div className="subcard-tag-group">
                          <span className="subcard-icon-circle">↗</span>
                          <span className="subcard-tag-label">OBSERVED DISCOVERY</span>
                        </div>
                        <span className="subcard-badge-calc">Calculated</span>
                      </div>
                      <h4 className="observed-discovery-heading">Your sales were higher on weekends than on weekdays.</h4>
                      <p className="observed-discovery-explanation">
                        We compared sales across different days and found that weekends brought in <strong>42% more sales</strong> on average during the period shown.
                      </p>
                    </div>

                    <div className="suggested-step-card">
                      <div className="suggested-step-tag">
                        <span className="sparkle-icon">✦</span>
                        <span>SUGGESTED NEXT STEP</span>
                      </div>
                      <p className="suggested-step-description">
                        Look at which products sell best on weekends. This could help you plan barista shifts, fresh milk orders, and morning pastry stock.
                      </p>
                    </div>
                  </>
                )}

                {/* Tab 2: Ask OmniLens Interactive Chat Content */}
                {heroPreviewTab === "ask" && (
                  <div className="preview-chat-container">
                    <div className="chat-bubble-user">{previewChatAnswer.q}</div>
                    <div className="chat-bubble-assistant">
                      <strong>OmniLens Answer</strong>
                      <p>{previewChatAnswer.a}</p>
                      <small>✓ {previewChatAnswer.method}</small>
                    </div>
                    <div className="preview-quick-prompts">
                      <button
                        className="quick-prompt-pill"
                        onClick={() =>
                          setPreviewChatAnswer({
                            q: "What are the peak hours?",
                            a: "Saturday and Sunday mornings between 8:00 AM and 11:30 AM saw 58% of all beverage orders.",
                            method: "Analyzed timestamp distribution across weekend transactions.",
                          })
                        }
                      >
                        Peak hours?
                      </button>
                      <button
                        className="quick-prompt-pill"
                        onClick={() =>
                          setPreviewChatAnswer({
                            q: "Which payment method was most used?",
                            a: "UPI was used for 64% of payments, followed by card (22%) and cash (14%).",
                            method: "Calculated payment method distribution across 84 records.",
                          })
                        }
                      >
                        Payment methods?
                      </button>
                      <button
                        className="quick-prompt-pill"
                        onClick={() =>
                          setPreviewChatAnswer({
                            q: "Which product generated the highest margin?",
                            a: "Caramel Macchiato generated a 78% gross margin, contributing ₹18,400 in profit. Top weekend performer.",
                            method: "Calculated by comparing unit prices with inventory costs across 84 sales transactions.",
                          })
                        }
                      >
                        Highest margin?
                      </button>
                    </div>
                  </div>
                )}

                {/* Tab 3: Quick Trend Chart Content */}
                {heroPreviewTab === "trend" && (
                  <div className="preview-trend-container">
                    <div className="preview-trend-chart-wrap">
                      <ResponsiveContainer width="100%" height={165}>
                        <BarChart data={HERO_WEEKEND_TREND} margin={{ top: 8, right: 6, bottom: 4, left: -16 }}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5DFC8" />
                          <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#66736B" }} axisLine={{ stroke: "#E5DFC8" }} />
                          <YAxis tick={{ fontSize: 10, fill: "#66736B" }} axisLine={false} tickFormatter={(v) => `₹${v / 1000}k`} />
                          <Tooltip
                            formatter={(val) => [`₹${val.toLocaleString()}`, "Sales"]}
                            contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #D4E4D3", fontSize: "12px" }}
                          />
                          <Bar dataKey="sales" radius={[4, 4, 0, 0]}>
                            {HERO_WEEKEND_TREND.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.isWeekend ? "#006241" : "#00754A"} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <p className="preview-trend-caption">
                      <strong>Weekend Spike:</strong> Saturday and Sunday average ₹27,650 vs weekday average of ₹14,400.
                    </p>
                  </div>
                )}

                <div className="preview-card-footer">
                  <span className="calc-verified-badge">✓ 100% Calculated from data</span>
                  <span className="sample-disclaimer">Sample preview shown</span>
                </div>
              </div>
            </div>
          </section>

          {/* ====================================================================
              TRUST STRIP (Directly Under Hero)
              ==================================================================== */}
          <section className="trust-strip">
            <div className="trust-container">
              <div className="trust-item">
                <div className="trust-icon-box">✦</div>
                <div className="trust-text">
                  <h3>Understand your data without coding.</h3>
                  <p>Plain-English summaries, intuitive charts, and zero formulas or programming required.</p>
                </div>
              </div>
              <div className="trust-item">
                <div className="trust-icon-box">🔍</div>
                <div className="trust-text">
                  <h3>See the evidence behind your findings.</h3>
                  <p>Every discovery links directly to the underlying rows and records so you can verify the facts.</p>
                </div>
              </div>
              <div className="trust-item">
                <div className="trust-icon-box">🌱</div>
                <div className="trust-text">
                  <h3>Turn discoveries into practical next steps.</h3>
                  <p>Get actionable suggestions you can use right away to plan inventory, costs, and decisions.</p>
                </div>
              </div>
            </div>
          </section>

          {/* ====================================================================
              INTERACTIVE DATA UPLOAD EXPERIENCE (Section 6A)
              ==================================================================== */}
          <section className="section-wrapper bg-cream" id="upload-section">
            <div className="section-container">
              <div className="section-header">
                <span className="section-eyebrow">YOUR DATA, CLEARLY EXPLAINED</span>
                <h2 className="section-title">Upload Your Dataset in Seconds</h2>
                <p className="section-subtitle">
                  Drop in your spreadsheet, CSV, or records. OmniLens reads the structure, performs safety checks, and creates understandable findings.
                </p>
              </div>

              <div className="upload-card-wrapper">
                <div
                  className={`upload-dropzone ${dragActive ? "drag-active" : ""}`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => document.getElementById("main-file-input")?.click()}
                >
                  <input
                    id="main-file-input"
                    type="file"
                    accept=".csv,.xlsx,.xls,.json,.txt,.html,.htm,.pdf"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                  <div className="upload-icon-circle">↑</div>
                  <h3>{t.uploadTitle}</h3>
                  <p>{t.uploadSub}</p>

                  <div className="upload-format-chips">
                    <span className="format-chip">CSV</span>
                    <span className="format-chip">Excel (.xlsx)</span>
                    <span className="format-chip">JSON</span>
                    <span className="format-chip">TXT</span>
                    <span className="format-chip">HTML</span>
                    <span className="format-chip">PDF Tables</span>
                    <span className="format-chip coming-soon">Images (Coming Soon)</span>
                  </div>

                  <div
                    className="upload-privacy-banner"
                    onClick={(e) => {
                      e.stopPropagation();
                      loadPrivacyAudit();
                      setPrivacyModalOpen(true);
                    }}
                    role="button"
                    tabIndex={0}
                    title="Click to view full technical zero-retention guarantee"
                  >
                    <span className="privacy-badge-icon">🔒</span>
                    <span><strong>Zero-Retention Guarantee:</strong> Processed in RAM only. Zero disk or database storage.</span>
                    <span className="privacy-verify-link">Verify Architecture →</span>
                  </div>
                </div>

                {file && (
                  <div className="file-selected-box">
                    <div className="file-info">
                      <span>📄</span>
                      <div>
                        <strong>{file.name}</strong>
                        <small>{(file.size / 1024).toFixed(1)} KB</small>
                      </div>
                    </div>
                    <button className="remove-file-btn" onClick={() => setFile(null)}>
                      Remove
                    </button>
                  </div>
                )}

                <button
                  className="primary-btn upload-action-btn"
                  onClick={() => analyzeFile(file)}
                  disabled={!file || busy}
                >
                  {busy ? t.working : file ? t.analyze : t.browse}
                </button>

                {busy && (
                  <div className="loading-indicator-row">
                    <span className="spinner-circle" />
                    <span>{t.working}</span>
                  </div>
                )}

                <div className="privacy-banner">
                  <span className="privacy-icon">🛡️</span>
                  <div>
                    <strong>Privacy Guarantee:</strong> {t.privacy}
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* ====================================================================
              SAMPLE DATASET EXPLORER (Section 6B)
              ==================================================================== */}
          <section className="section-wrapper" id="samples-section">
            <div className="section-container">
              <div className="section-header">
                <span className="section-eyebrow">READY-TO-EXPLORE DEMOS</span>
                <h2 className="section-title">{t.examplesTitle}</h2>
                <p className="section-subtitle">{t.sampleSub}</p>
              </div>

              <div className="samples-grid">
                {/* Sample 1: Business */}
                <button className="sample-explorer-card" onClick={() => loadSample("shop")} disabled={busy}>
                  <div className="sample-card-header">
                    <span className="sample-category-icon">🏪</span>
                    <div className="sample-header-text">
                      <h3>{t.shop}</h3>
                      <p>{t.shopDesc}</p>
                    </div>
                  </div>
                  <div className="sample-meta-row">
                    <span className="sample-meta-pill">290 records</span>
                    <span className="sample-meta-pill">16 fields</span>
                    <span className="sample-meta-pill">Business & Sales</span>
                  </div>
                  <span className="sample-btn-action">{t.trySample} →</span>
                </button>

                {/* Sample 2: Personal Finance */}
                <button className="sample-explorer-card" onClick={() => loadSample("expenses")} disabled={busy}>
                  <div className="sample-card-header">
                    <span className="sample-category-icon">💳</span>
                    <div className="sample-header-text">
                      <h3>{t.expenses}</h3>
                      <p>{t.expensesDesc}</p>
                    </div>
                  </div>
                  <div className="sample-meta-row">
                    <span className="sample-meta-pill">270 records</span>
                    <span className="sample-meta-pill">14 fields</span>
                    <span className="sample-meta-pill">Personal Money</span>
                  </div>
                  <span className="sample-btn-action">{t.trySample} →</span>
                </button>

                {/* Sample 3: Government Tax */}
                <button className="sample-explorer-card" onClick={() => loadSample("tax")} disabled={busy}>
                  <div className="sample-card-header">
                    <span className="sample-category-icon">🏛️</span>
                    <div className="sample-header-text">
                      <h3>{t.tax}</h3>
                      <p>{t.taxDesc}</p>
                    </div>
                  </div>
                  <div className="sample-meta-row">
                    <span className="sample-meta-pill">District Report</span>
                    <span className="sample-meta-pill">Weighted Averages</span>
                    <span className="sample-meta-pill">Public Finance</span>
                  </div>
                  <span className="sample-btn-action">{t.trySample} →</span>
                </button>

                {/* Sample 4: Crime Statistics */}
                <button className="sample-explorer-card" onClick={() => loadSample("crime")} disabled={busy}>
                  <div className="sample-card-header">
                    <span className="sample-category-icon">🚓</span>
                    <div className="sample-header-text">
                      <h3>{t.crime}</h3>
                      <p>{t.crimeDesc}</p>
                    </div>
                  </div>
                  <div className="sample-meta-row">
                    <span className="sample-meta-pill">305 incidents</span>
                    <span className="sample-meta-pill">Districts & Follow-ups</span>
                    <span className="sample-meta-pill">Public Services</span>
                  </div>
                  <span className="sample-btn-action">{t.trySample} →</span>
                </button>
              </div>
            </div>
          </section>

          {/* ====================================================================
              HOW IT WORKS SECTION
              ==================================================================== */}
          <section className="section-wrapper bg-cream" id="how-it-works-section">
            <div className="section-container">
              <div className="section-header">
                <span className="section-eyebrow">FOUR SIMPLE STEPS</span>
                <h2 className="section-title">How OmniLens Works</h2>
                <p className="section-subtitle">From raw numbers to actionable decisions without a steep learning curve.</p>
              </div>

              <div className="steps-grid">
                <div className="step-card">
                  <span className="step-number-badge">1</span>
                  <h3>Upload or Pick a Sample</h3>
                  <p>Choose an Excel sheet, CSV, or test with our ready-made coffee shop or expense ledger examples.</p>
                </div>
                <div className="step-card">
                  <span className="step-number-badge">2</span>
                  <h3>Plain-English Analysis</h3>
                  <p>OmniLens analyzes columns, checks data quality, and calculates significant patterns automatically.</p>
                </div>
                <div className="step-card">
                  <span className="step-number-badge">3</span>
                  <h3>Explore & Verify</h3>
                  <p>Browse beautiful interactive charts, click any finding to inspect underlying rows, and review evidence.</p>
                </div>
                <div className="step-card">
                  <span className="step-number-badge">4</span>
                  <h3>Ask Questions & Export</h3>
                  <p>Ask questions in natural English and download clean professional PDF, Word, or cleaned Excel files.</p>
                </div>
              </div>
            </div>
          </section>

          {/* ====================================================================
              FEATURES SECTION
              ==================================================================== */}
          <section className="section-wrapper" id="features-section">
            <div className="section-container">
              <div className="section-header">
                <span className="section-eyebrow">POWERFUL YET INTUITIVE</span>
                <h2 className="section-title">Built for Everyone, Not Just Analysts</h2>
                <p className="section-subtitle">Everything you need to turn raw data into informed action.</p>
              </div>

              <div className="features-grid">
                <div className="feature-item-card">
                  <div className="feature-icon-wrapper">💬</div>
                  <h3>Natural-Language Q&A</h3>
                  <p>Ask questions like "Which product had the highest return rate?" and get direct answers backed by numbers.</p>
                </div>
                <div className="feature-item-card">
                  <div className="feature-icon-wrapper">🔍</div>
                  <h3>Evidence Behind Findings</h3>
                  <p>No black boxes. Click any discovery to see the exact records that prove and substantiate the conclusion.</p>
                </div>
                <div className="feature-item-card">
                  <div className="feature-icon-wrapper">🧹</div>
                  <h3>One-Click Data Cleaning</h3>
                  <p>Preview suggested fixes for typos, whitespace, and duplicates before downloading a clean copy.</p>
                </div>
                <div className="feature-item-card">
                  <div className="feature-icon-wrapper">📊</div>
                  <h3>Starbucks-Inspired Charts</h3>
                  <p>Clear bar and line charts styled in warm greens and creams that make trends easy to understand.</p>
                </div>
                <div className="feature-item-card">
                  <div className="feature-icon-wrapper">📄</div>
                  <h3>Comprehensive Export</h3>
                  <p>Download ready-to-share PDF documents, Word reports, WhatsApp text summaries, or print directly.</p>
                </div>
                <div className="feature-item-card">
                  <div className="feature-icon-wrapper">⇄</div>
                  <h3>File Comparison</h3>
                  <p>Upload earlier and later periods to automatically compare revenue, volume, and shifting patterns.</p>
                </div>
              </div>
            </div>
          </section>
        </>
      )}

      {/* ====================================================================
          FRIENDLY ANALYTICS DASHBOARD (Section 7)
          Rendered when a dataset is active / analyzed
          ==================================================================== */}
      {result && analysis && (
        <main className="dashboard-view">
          {/* Dashboard Header Bar */}
          <section className="dashboard-header-bar">
            <div className="dashboard-header-container">
              <div className="dataset-badge-cluster">
                <span className="dataset-file-chip">📄 {result.filename}</span>
                <span className="dataset-meta-pill">
                  {analysis.shape?.shape === "grouped_summary" ? "Rows in report" : t.imported}:{" "}
                  <strong>{result.import_report?.rows_read?.toLocaleString() || analysis.row_count.toLocaleString()}</strong>
                </span>
                <span className="dataset-meta-pill">
                  Fields: <strong>{analysis.column_count}</strong>
                </span>
                <span className="dataset-quality-pill">
                  ✓ Quality Checked: {analysis.shape?.shape?.replaceAll("_", " ")}
                </span>
              </div>

              <div className="dashboard-top-actions">
                <button className="speak-action-btn" onClick={() => speak(`${analysis.headline}. ${analysis.caveat}`)}>
                  🔊 {t.read}
                </button>
                <button className="change-file-btn" onClick={changeFile}>
                  <span>↑ {t.uploadAgain}</span>
                </button>
              </div>
            </div>
          </section>

          {/* ZERO-RETENTION TRUST HUD BAR */}
          <div className="zero-retention-hud">
            <div className="hud-container">
              <div className="hud-status">
                <span className="hud-shield-icon" aria-hidden="true">🔒</span>
                <div>
                  <div className="hud-title-row">
                    <strong>Zero-Retention Mode: Active</strong>
                    <span className="hud-ram-badge">100% In-RAM</span>
                  </div>
                  <div className="hud-desc">Transient volatile memory · Zero disk writes · No database</div>
                </div>
              </div>

              <div className="hud-actions">
                <div className="hud-countdown" title="Session automatically purges after inactivity">
                  <span className="hud-pulse-dot"></span>
                  <span>Purging in: <strong>{Math.floor(sessionTimeLeft / 60)}:{String(sessionTimeLeft % 60).padStart(2, "0")}</strong></span>
                </div>
                <button
                  type="button"
                  className="hud-proof-btn"
                  onClick={() => {
                    loadPrivacyAudit();
                    setPrivacyModalOpen(true);
                  }}
                  title="View technical zero-retention audit and facts"
                >
                  🛡️ Privacy Proof
                </button>
                <button
                  type="button"
                  className="hud-burn-btn"
                  onClick={() => burnSession(false)}
                  title="Instantly wipe dataset & session from RAM"
                >
                  🔥 Burn Data Now
                </button>
              </div>
            </div>
          </div>

          {/* Low confidence shape question if applicable */}
          {analysis.shape?.confidence === "low" && (
            <div style={{ maxWidth: "1240px", margin: "16px auto 0", padding: "0 28px" }}>
              <section className="clean-item-box" style={{ background: "var(--warning-bg)", border: "1px solid var(--warning-border)" }}>
                <h3 style={{ fontSize: "15px", color: "var(--warning)", marginBottom: "8px" }}>{t.rowQuestion}</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "8px", marginBottom: "10px" }}>
                  {[
                    ["person_or_transaction", t.person],
                    ["group_or_summary", t.group],
                    ["measurements_over_time", t.time],
                    ["list_of_names_or_contacts", t.contact],
                    ["written_comments", t.textRows],
                    ["area_or_district_summary", t.placeRows],
                    ["not_sure", t.notSure],
                  ].map(([val, label]) => (
                    <label key={val} style={{ fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                      <input
                        type="radio"
                        name="rowMeaning"
                        value={val}
                        checked={rowMeaning === val}
                        onChange={(e) => setRowMeaning(e.target.value)}
                      />
                      {label}
                    </label>
                  ))}
                </div>
                <button className="secondary-btn" style={{ minHeight: "36px", padding: "6px 16px", fontSize: "13px" }} onClick={confirmRows}>
                  {t.continue}
                </button>
              </section>
            </div>
          )}

          {/* Sticky Dashboard Tab Navigation */}
          <nav className="dashboard-tabs-bar" aria-label="Dashboard views">
            <div className="dashboard-tabs-container">
              <button
                className={`dash-tab-btn ${dashTab === "overview" ? "active" : ""}`}
                onClick={() => setDashTab("overview")}
              >
                <span>✦</span> Overview
              </button>
              <button
                className={`dash-tab-btn ${dashTab === "explore" ? "active" : ""}`}
                onClick={() => setDashTab("explore")}
              >
                <span>📊</span> Explore Charts ({analysis.charts?.length || 0})
              </button>
              <button
                className={`dash-tab-btn ${dashTab === "findings" ? "active" : ""}`}
                onClick={() => setDashTab("findings")}
              >
                <span>💡</span> Findings ({analysis.findings?.length || 0})
              </button>
              <button
                className={`dash-tab-btn ${dashTab === "ask" ? "active" : ""}`}
                onClick={() => setDashTab("ask")}
              >
                <span>💬</span> Ask Your Data
              </button>
              <button
                className={`dash-tab-btn ${dashTab === "quality" ? "active" : ""}`}
                onClick={() => setDashTab("quality")}
              >
                <span>🧹</span> Data Quality
              </button>
              <button
                className={`dash-tab-btn ${dashTab === "reports" ? "active" : ""}`}
                onClick={() => setDashTab("reports")}
              >
                <span>📄</span> Reports & Compare
              </button>
            </div>
          </nav>

          <div className="dashboard-body-wrap">
            {/* 1. OVERVIEW TAB */}
            {dashTab === "overview" && (
              <>
                <section className="overview-headline-card">
                  <div className="headline-kicker-row">
                    <span className="headline-kicker">{t.result}</span>
                    <span className="calc-verified-badge">✓ Verified from source rows</span>
                  </div>
                  <h2 className="overview-headline-text">{analysis.headline}</h2>
                  <div className="caveat-box">
                    <strong>{t.limit}:</strong> {analysis.caveat}
                  </div>
                </section>

                <div className="summary-stats-grid">
                  <div className="stat-card">
                    <span className="stat-card-label">Total Records</span>
                    <span className="stat-card-value">{analysis.row_count.toLocaleString()}</span>
                    <span className="stat-card-detail">Rows of information</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-card-label">Total Columns</span>
                    <span className="stat-card-value">{analysis.column_count}</span>
                    <span className="stat-card-detail">Fields of detail</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-card-label">Key Discoveries</span>
                    <span className="stat-card-value">{analysis.findings?.length || 0}</span>
                    <span className="stat-card-detail">Evidence-backed findings</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-card-label">Action Items</span>
                    <span className="stat-card-value">{(analysis.actions || []).length}</span>
                    <span className="stat-card-detail">Recommended next steps</span>
                  </div>
                </div>

                {/* Primary Chart on Overview */}
                {analysis.charts?.[0] && (
                  <div className="chart-card-box">
                    <div className="chart-header-row">
                      <h3>{analysis.charts[0].title}</h3>
                      <p>{analysis.charts[0].explanation}</p>
                    </div>
                    <div className="chart-render-wrap">
                      <ResponsiveContainer width="100%" height={250}>
                        {analysis.charts[0].labels.length > 7 ? (
                          <LineChart
                            data={analysis.charts[0].labels.map((label, idx) => ({ label, value: analysis.charts[0].values[idx] }))}
                            margin={{ top: 10, right: 15, bottom: 25, left: 10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5DFC8" />
                            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#66736B" }} angle={-15} textAnchor="end" interval={0} />
                            <YAxis tick={{ fontSize: 11, fill: "#66736B" }} />
                            <Tooltip contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #D4E4D3" }} />
                            <Line type="monotone" dataKey="value" stroke="#006241" strokeWidth={3} dot={{ r: 4, fill: "#006241" }} />
                          </LineChart>
                        ) : (
                          <BarChart
                            data={analysis.charts[0].labels.map((label, idx) => ({ label, value: analysis.charts[0].values[idx] }))}
                            margin={{ top: 10, right: 15, bottom: 25, left: 10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5DFC8" />
                            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#66736B" }} />
                            <YAxis tick={{ fontSize: 11, fill: "#66736B" }} />
                            <Tooltip contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #D4E4D3" }} />
                            <Bar dataKey="value" fill="#006241" radius={[6, 6, 0, 0]} />
                          </BarChart>
                        )}
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {/* Recommended Next Steps Checklist */}
                <section className="checklist-card">
                  <div className="checklist-title-row">
                    <h3>{t.next}</h3>
                    <p>Practical next actions recommended from your data. Check them off as you review.</p>
                  </div>
                  <div className="checklist-items">
                    {(analysis.actions || []).slice(0, 5).map((action, idx) => (
                      <label
                        className={`checklist-item-row ${doneActions[idx] ? "is-completed" : ""}`}
                        key={`${action.title}-${idx}`}
                      >
                        <input
                          type="checkbox"
                          checked={!!doneActions[idx]}
                          onChange={() => setDoneActions((old) => ({ ...old, [idx]: !old[idx] }))}
                        />
                        <div className="checklist-content">
                          <strong>{action.title}</strong>
                          <small>
                            {action.detail} {action.action}
                          </small>
                        </div>
                      </label>
                    ))}
                  </div>
                </section>
              </>
            )}

            {/* 2. EXPLORE DATA (CHARTS) TAB */}
            {dashTab === "explore" && (
              <>
                <div className="section-header" style={{ marginBottom: "20px", textAlign: "left" }}>
                  <span className="section-eyebrow">VISUAL DISCOVERIES</span>
                  <h2 className="section-title">{t.charts}</h2>
                  <p className="section-subtitle">Interactive visualisations calculated from your uploaded records.</p>
                </div>

                <div className="chart-grid-layout">
                  {(analysis.charts || []).map((chart, i) => (
                    <div className={`chart-card-box ${i === 0 ? "featured-chart" : ""}`} key={`${chart.title}-${i}`}>
                      <div className="chart-header-row">
                        <h3>{chart.title}</h3>
                        <p>{chart.explanation}</p>
                      </div>
                      <div className="chart-render-wrap">
                        <ResponsiveContainer width="100%" height={250}>
                          {chart.labels.length > 7 ? (
                            <LineChart
                              data={chart.labels.map((label, idx) => ({ label, value: chart.values[idx] }))}
                              margin={{ top: 8, right: 12, bottom: 25, left: 4 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5DFC8" />
                              <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#66736B" }} angle={-18} textAnchor="end" interval={0} />
                              <YAxis tick={{ fontSize: 10, fill: "#66736B" }} />
                              <Tooltip contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #D4E4D3" }} />
                              <Line type="monotone" dataKey="value" stroke="#006241" strokeWidth={3} dot={{ r: 4, fill: "#006241" }} />
                            </LineChart>
                          ) : (
                            <BarChart
                              data={chart.labels.map((label, idx) => ({ label, value: chart.values[idx] }))}
                              margin={{ top: 8, right: 12, bottom: 25, left: 4 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5DFC8" />
                              <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#66736B" }} angle={-10} textAnchor="end" />
                              <YAxis tick={{ fontSize: 10, fill: "#66736B" }} />
                              <Tooltip contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #D4E4D3" }} />
                              <Bar dataKey="value" fill="#006241" radius={[5, 5, 0, 0]} />
                            </BarChart>
                          )}
                        </ResponsiveContainer>
                      </div>
                    </div>
                  ))}
                </div>

                <details style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "12px", padding: "14px 18px", marginTop: "14px" }}>
                  <summary style={{ fontWeight: 700, cursor: "pointer", color: "var(--dark-green)" }}>
                    🔍 {t.more}
                  </summary>
                  <div style={{ marginTop: "10px", fontSize: "12.5px", color: "var(--muted-grey)", lineHeight: 1.6 }}>
                    <p><strong>Detected Dataset Purpose:</strong> {analysis.shape?.shape?.replaceAll("_", " ")}</p>
                    <p>{analysis.shape?.reason}</p>
                    <p><strong>Rows Read:</strong> {analysis.row_count.toLocaleString()} · <strong>Columns:</strong> {analysis.column_count}</p>
                    {analysis.date_notes && <p><strong>Date Formats:</strong> {analysis.date_notes}</p>}
                    <p><strong>Privacy:</strong> {result.privacy}</p>
                  </div>
                </details>
              </>
            )}

            {/* 3. FINDINGS TAB */}
            {dashTab === "findings" && (
              <>
                <div className="section-header" style={{ marginBottom: "20px", textAlign: "left" }}>
                  <span className="section-eyebrow">WHAT YOUR DATA SAYS</span>
                  <h2 className="section-title">{t.findings}</h2>
                  <p className="section-subtitle">
                    Each card highlights one pattern. Click "See source rows" to examine the exact supporting data.
                  </p>
                </div>

                <div className="findings-list-wrapper">
                  {(analysis.findings || []).map((finding, idx) => (
                    <article className="finding-card-item" key={finding.id}>
                      <div className="finding-index-circle">{idx + 1}</div>
                      <div className="finding-content-col">
                        <span className="finding-category-tag">{finding.category}</span>
                        <h3>{finding.title}</h3>
                        <p className="finding-happened-text">{finding.happened}</p>

                        <div className="evidence-box">
                          <strong>What supports this:</strong> {finding.evidence}
                        </div>

                        <div className="next-step-box">
                          <strong>Recommended action:</strong> {finding.next_step}
                        </div>

                        <div>
                          <button className="see-evidence-btn" onClick={() => showEvidence(finding)}>
                            ↳ {t.evidence} ({finding.rows?.length || 0} rows)
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </>
            )}

            {/* 4. ASK YOUR DATA TAB */}
            {dashTab === "ask" && (
              <section className="ask-interface-card">
                <div className="ask-header">
                  <h2>{t.ask}</h2>
                  <p>Type a question about products, dates, totals, or trends in plain everyday words.</p>
                </div>

                <div className="ask-input-row">
                  <input
                    className="ask-text-input"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && askQuestion()}
                    placeholder={isListening ? "🎙️ Listening... speak your question now" : t.askHint}
                    aria-label={t.askHint}
                  />
                  <button
                    type="button"
                    className={`voice-mic-btn ${isListening ? "listening" : ""}`}
                    onClick={toggleVoiceInput}
                    title="Ask with voice (English, Hindi, Marathi)"
                    aria-label="Ask with voice"
                  >
                    {isListening ? (
                      <span className="mic-listening-pulse">🔴</span>
                    ) : (
                      <span>🎤</span>
                    )}
                  </button>
                  <button
                    className="ask-submit-btn"
                    onClick={() => askQuestion()}
                    disabled={asking || !question.trim()}
                  >
                    {asking ? t.loading : t.askButton}
                  </button>
                </div>

                {suggested.length > 0 && (
                  <div className="suggested-questions-tray">
                    <span style={{ fontSize: "12px", color: "var(--muted-grey)", fontWeight: 700 }}>Suggestions:</span>
                    {suggested.slice(0, 4).map((q, i) => (
                      <button key={i} className="suggested-q-pill" onClick={() => askQuestion(q)}>
                        {q}
                      </button>
                    ))}
                  </div>
                )}

                {answer && (
                  <div className="answer-display-box">
                    <span className="answer-badge-tag">OmniLens Direct Answer</span>
                    <h3 className="answer-main-text">{answer.answer}</h3>
                    <p className="answer-calculation-method">
                      <strong>Method:</strong> {answer.how_calculated}
                    </p>

                    {answer.chart && (
                      <div className="answer-chart-wrap">
                        <ResponsiveContainer width="100%" height={200}>
                          <BarChart data={answer.chart.labels.map((label, i) => ({ label, value: answer.chart.values[i] }))}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5DFC8" />
                            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#66736B" }} />
                            <YAxis tick={{ fontSize: 11, fill: "#66736B" }} />
                            <Tooltip contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #D4E4D3" }} />
                            <Bar dataKey="value" fill="#006241" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    {answer.rows?.length > 0 && (
                      <div className="table-preview-wrap">
                        <table>
                          <thead>
                            <tr>
                              {Object.keys(answer.rows[0]).map((k) => (
                                <th key={k}>{k}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {answer.rows.slice(0, 6).map((row, i) => (
                              <tr key={i}>
                                {Object.values(row).map((v, j) => (
                                  <td key={j}>{String(v ?? "—")}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    <div className="caveat-box" style={{ marginTop: "8px" }}>
                      <strong>{t.limit}:</strong> {answer.what_this_cannot_tell_us}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* 5. DATA QUALITY TAB */}
            {dashTab === "quality" && (
              <section className="quality-summary-card">
                <div>
                  <span className="section-eyebrow">QUALITY REPORT</span>
                  <h2 className="section-title">Data Health & Structure</h2>
                  <p className="section-subtitle">
                    OmniLens scanned your records for missing cells, unusual formatting, duplicates, and structure.
                  </p>
                </div>

                <div className="summary-stats-grid">
                  <div className="stat-card">
                    <span className="stat-card-label">Shape</span>
                    <span className="stat-card-value" style={{ fontSize: "18px" }}>
                      {analysis.shape?.shape?.replaceAll("_", " ")}
                    </span>
                    <span className="stat-card-detail">{analysis.shape?.confidence} confidence</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-card-label">Import Method</span>
                    <span className="stat-card-value" style={{ fontSize: "18px" }}>
                      {result.import_report?.method || "Standard"}
                    </span>
                    <span className="stat-card-detail">Encoding & delimiters parsed</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-card-label">Privacy Shield</span>
                    <span className="stat-card-value" style={{ fontSize: "18px", color: "var(--fresh-green)" }}>
                      Active
                    </span>
                    <span className="stat-card-detail">Held in-memory only</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-card-label">Cleaner Status</span>
                    <span className="stat-card-value" style={{ fontSize: "18px" }}>Ready</span>
                    <span className="stat-card-detail">Safe preview available</span>
                  </div>
                </div>

                <div style={{ marginTop: "14px" }}>
                  <button className="primary-btn" onClick={openCleaning}>
                    <span>🧹 {t.clean} (Review & Normalise)</span>
                  </button>
                  <p style={{ fontSize: "12px", color: "var(--muted-grey)", marginTop: "6px" }}>{t.cleanNote}</p>
                </div>
              </section>
            )}

            {/* 6. REPORTS & COMPARE TAB */}
            {dashTab === "reports" && (
              <div className="reports-tools-grid">
                {/* Export Card */}
                <div className="tool-card-item">
                  <div>
                    <span className="section-eyebrow">EXPORTS & SHARING</span>
                    <h3>Download Reports</h3>
                    <p>{t.shareDesc}</p>
                  </div>

                  <div className="export-buttons-row">
                    <button className="export-btn" onClick={() => downloadReport("pdf")}>
                      📄 {t.pdf}
                    </button>
                    <button className="export-btn" onClick={() => downloadReport("docx")}>
                      📝 {t.word}
                    </button>
                    <button className="export-btn" onClick={copyWhatsApp}>
                      💬 {t.whatsapp}
                    </button>
                    <button className="export-btn" onClick={() => window.print()}>
                      🖨️ {t.print}
                    </button>
                  </div>
                </div>

                {/* Compare Card */}
                <div className="tool-card-item">
                  <div>
                    <span className="section-eyebrow">DIFFERENCE DETECTION</span>
                    <h3>{t.compare}</h3>
                    <p>{t.compareHelp}</p>
                  </div>

                  <div className="compare-box-expanded">
                    <p style={{ fontSize: "12px", color: "var(--muted-grey)" }}>
                      {t.compareSamples}{" "}
                      <a href={`${API}/api/sample-file/shop_earlier`}>{t.compareEarlier}</a> ·{" "}
                      <a href={`${API}/api/sample-file/shop_later`}>{t.compareLater}</a>
                    </p>

                    <div className="compare-file-inputs">
                      <label className="compare-input-label">
                        <span>{t.selectF}</span>
                        <input
                          type="file"
                          accept=".csv,.xlsx,.xls,.json,.txt,.html,.pdf"
                          onChange={(e) => setCompareA(e.target.files?.[0] || null)}
                        />
                      </label>
                      <label className="compare-input-label">
                        <span>{t.selectS}</span>
                        <input
                          type="file"
                          accept=".csv,.xlsx,.xls,.json,.txt,.html,.pdf"
                          onChange={(e) => setCompareB(e.target.files?.[0] || null)}
                        />
                      </label>
                    </div>

                    <button
                      className="secondary-btn"
                      style={{ alignSelf: "flex-start", minHeight: "42px" }}
                      onClick={compareFiles}
                      disabled={busy}
                    >
                      {t.compareRun}
                    </button>

                    {compareResult && (
                      <div className="clean-item-box" style={{ marginTop: "12px" }}>
                        <h4 style={{ fontSize: "14px", color: "var(--dark-green)", marginBottom: "6px" }}>
                          {compareResult.headline}
                        </h4>
                        {compareResult.differences?.length > 0 && (
                          <div className="table-preview-wrap">
                            <table>
                              <thead>
                                <tr>
                                  {Object.keys(compareResult.differences[0]).map((k) => (
                                    <th key={k}>{k}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {compareResult.differences.map((r, i) => (
                                  <tr key={i}>
                                    {Object.values(r).map((v, j) => (
                                      <td key={j}>
                                        {typeof v === "number"
                                          ? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
                                          : String(v ?? "—")}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        <p style={{ fontSize: "11px", color: "var(--muted-grey)", marginTop: "6px" }}>
                          {compareResult.caveat}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      )}

      {/* ====================================================================
          EVIDENCE MODAL (Source Rows Inspector)
          ==================================================================== */}
      {evidenceFinding && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label={t.evidence}>
          <div className="modal-dialog">
            <div className="modal-header-row">
              <div>
                <span className="section-eyebrow">SOURCE EVIDENCE RECORDS</span>
                <h2>{evidenceFinding.title}</h2>
                <p>Verifying the observations that formed this discovery.</p>
              </div>
              <button
                className="modal-close-icon"
                onClick={() => {
                  setEvidenceFinding(null);
                  setEvidence(null);
                }}
                aria-label={t.close}
              >
                ×
              </button>
            </div>

            {evidence ? (
              <>
                <p style={{ fontSize: "13px", color: "var(--muted-grey)" }}>
                  {evidence.message} {evidence.count} source row(s) displayed.
                </p>
                <div className="table-preview-wrap" style={{ maxHeight: "45vh" }}>
                  <table>
                    <thead>
                      <tr>
                        {Object.keys(evidence.rows[0] || {}).map((k) => (
                          <th key={k}>{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {evidence.rows.slice(0, 50).map((row, i) => (
                        <tr key={i}>
                          {Object.values(row).map((v, j) => (
                            <td key={j}>{String(v ?? "—")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <a
                    className="see-evidence-btn"
                    style={{ fontSize: "13px" }}
                    href={`${API}/api/evidence/${session}/${evidenceFinding.id}/excel`}
                  >
                    📥 {t.downloadRows}
                  </a>
                </div>
              </>
            ) : (
              <div className="loading-indicator-row">Loading source records…</div>
            )}

            <div className="modal-footer-row">
              <button
                className="secondary-btn"
                style={{ minHeight: "42px" }}
                onClick={() => {
                  setEvidenceFinding(null);
                  setEvidence(null);
                }}
              >
                {t.close}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ====================================================================
          DATA CLEANING MODAL
          ==================================================================== */}
      {cleanOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label={t.clean}>
          <div className="modal-dialog" style={{ maxWidth: "780px" }}>
            <div className="modal-header-row">
              <div>
                <span className="section-eyebrow">DATA INTEGRITY ASSISTANT</span>
                <h2>{t.clean}</h2>
                <p>{t.cleanNote}</p>
              </div>
              <button className="modal-close-icon" onClick={() => setCleanOpen(false)} aria-label={t.close}>
                ×
              </button>
            </div>

            {!clean ? (
              <div className="loading-indicator-row">Preparing cleaning suggestions…</div>
            ) : (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <button
                    className="see-evidence-btn"
                    style={{ fontSize: "12.5px" }}
                    onClick={chooseSafeChanges}
                  >
                    ✓ {t.allSafe}
                  </button>
                  <span style={{ fontSize: "12px", color: "var(--muted-grey)" }}>
                    {clean.changes.length} suggestion(s) found
                  </span>
                </div>

                {clean.changes.length === 0 ? (
                  <p style={{ fontSize: "13px", color: "var(--muted-grey)" }}>{t.noChanges}</p>
                ) : (
                  clean.changes.map((change) => (
                    <div className="clean-item-box" key={change.id}>
                      <label className="clean-item-label">
                        <input
                          type="checkbox"
                          checked={cleanSelected.includes(change.id)}
                          onChange={() => toggleClean(change.id)}
                        />
                        <div className="clean-item-text">
                          <strong>{change.label}</strong>
                          <small>{change.description}</small>
                        </div>
                        {change.safe ? (
                          <span className="safe-indicator-badge">Safe</span>
                        ) : (
                          <span className="safe-indicator-badge" style={{ color: "var(--warning)", background: "var(--warning-bg)", borderColor: "var(--warning-border)" }}>
                            Review
                          </span>
                        )}
                      </label>

                      {change.id === "normalise_spelling" &&
                        change.suggestions?.map((s, i) => (
                          <label
                            key={i}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              padding: "6px 0 2px 24px",
                              fontSize: "12px",
                              cursor: "pointer",
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={!!spellMappings[`${s.field}-${i}`]}
                              onChange={(e) =>
                                setSpellMappings((old) => ({ ...old, [`${s.field}-${i}`]: e.target.checked }))
                              }
                            />
                            <span>
                              <strong>{s.field}:</strong> {s.variants.join(" / ")} → Use “{s.suggested_value}”
                            </span>
                          </label>
                        ))}
                    </div>
                  ))
                )}

                {/* Before / After Table Diff */}
                {clean.before?.length > 0 && (
                  <div style={{ marginTop: "12px" }}>
                    <h4 style={{ fontSize: "14px", color: "var(--dark-green)", marginBottom: "4px" }}>
                      {t.before} / {t.after} Live Preview
                    </h4>
                    <p style={{ fontSize: "12px", color: "var(--muted-grey)", marginBottom: "8px" }}>
                      Changes apply only to your downloaded copy; original upload is unchanged.
                    </p>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                      <div>
                        <strong style={{ fontSize: "11px", color: "var(--muted-grey)" }}>{t.before}</strong>
                        <div className="table-preview-wrap">
                          <table>
                            <thead>
                              <tr>
                                {Object.keys(cleanBeforeRows[0]).slice(0, 4).map((k) => (
                                  <th key={k}>{k}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {cleanBeforeRows.slice(0, 4).map((r, i) => (
                                <tr key={i}>
                                  {Object.keys(cleanBeforeRows[0]).slice(0, 4).map((k) => (
                                    <td key={k}>{String(r[k] ?? "—")}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      <div>
                        <strong style={{ fontSize: "11px", color: "var(--muted-grey)" }}>{t.after}</strong>
                        <div className="table-preview-wrap">
                          {cleanAfterRows.length > 0 ? (
                            <table>
                              <thead>
                                <tr>
                                  {Object.keys(cleanAfterRows[0]).slice(0, 4).map((k) => (
                                    <th key={k}>{k}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {cleanAfterRows.slice(0, 4).map((r, i) => (
                                  <tr key={i}>
                                    {Object.keys(cleanAfterRows[0]).slice(0, 4).map((k) => (
                                      <td key={k}>{String(r[k] ?? "—")}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : (
                            <p style={{ fontSize: "12px", padding: "10px", color: "var(--muted-grey)" }}>
                              No rows would remain with current selections.
                            </p>
                          )}
                        </div>
                      </div>
                    </div>

                    {cleanPreviewLoading && (
                      <p style={{ fontSize: "12px", color: "var(--deep-green)", marginTop: "6px" }}>
                        Updating preview…
                      </p>
                    )}
                  </div>
                )}

                <div className="modal-footer-row">
                  <button className="secondary-btn" onClick={() => setCleanOpen(false)}>
                    {t.close}
                  </button>
                  <button
                    className="primary-btn"
                    onClick={applyCleaning}
                    disabled={!cleanSelected.length}
                  >
                    {t.approve}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Error Toast Notification */}
      {error && (
        <div className="alert-toast" role="alert">
          <span>{error}</span>
          <button onClick={() => setError("")} aria-label="Dismiss alert">
            ×
          </button>
        </div>
      )}

      {/* ====================================================================
          ZERO-RETENTION PRIVACY PROOF MODAL
          ==================================================================== */}
      {privacyModalOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true" onClick={() => setPrivacyModalOpen(false)}>
          <div className="modal-dialog privacy-proof-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-row">
              <div>
                <span className="section-eyebrow">SECURITY & PRIVACY GUARANTEE</span>
                <h2>OmniLens Zero-Retention Architecture</h2>
                <p>Technical verification of how your uploaded data is handled in memory.</p>
              </div>
              <button className="modal-close-icon" onClick={() => setPrivacyModalOpen(false)} aria-label="Close modal">
                ×
              </button>
            </div>

            <div className="privacy-audit-grid">
              <div className="audit-item">
                <div className="audit-icon">💾</div>
                <div className="audit-text">
                  <h4>Zero Disk Writes</h4>
                  <p>Uploaded files are parsed strictly in process memory and never written to temporary files or server hard drives.</p>
                </div>
              </div>

              <div className="audit-item">
                <div className="audit-icon">🗄️</div>
                <div className="audit-text">
                  <h4>No Database Connected</h4>
                  <p>OmniLens operates with no SQL, PostgreSQL, MongoDB, DynamoDB, or Redis. There is no persistent database of uploads.</p>
                </div>
              </div>

              <div className="audit-item">
                <div className="audit-icon">⚡</div>
                <div className="audit-text">
                  <h4>Volatile In-Memory RAM</h4>
                  <p>Sessions exist only in transient RAM with an auto-expiring timer and completely vanish whenever the server process or container restarts.</p>
                </div>
              </div>

              <div className="audit-item">
                <div className="audit-icon">🚫</div>
                <div className="audit-text">
                  <h4>Zero Third-Party Trackers</h4>
                  <p>No Google Analytics, Meta Pixels, Hotjar, or third-party cookies. Your dataset queries remain 100% private.</p>
                </div>
              </div>

              <div className="audit-item">
                <div className="audit-icon">🔥</div>
                <div className="audit-text">
                  <h4>Instant Manual & Tab-Close Purge</h4>
                  <p>Clicking "Burn Data Now" or closing your browser tab immediately triggers a memory release and system garbage collection (<code>gc.collect()</code>).</p>
                </div>
              </div>

              <div className="audit-item">
                <div className="audit-icon">🛡️</div>
                <div className="audit-text">
                  <h4>Client-Side Masking</h4>
                  <p>Sensitive identifiers such as PAN, GSTIN, phone, and account numbers are masked before rendering in previews and exports.</p>
                </div>
              </div>
            </div>

            {privacyAuditData && (
              <div className="audit-live-status">
                <span className="live-tag">● LIVE SERVER ATTESTATION</span>
                <span>Active RAM Sessions: <strong>{privacyAuditData.active_ram_sessions}</strong></span>
                <span>Persistent Disk Writes: <strong>{String(privacyAuditData.persistent_disk_writes)}</strong></span>
                <span>Database Connected: <strong>{String(privacyAuditData.database_connected)}</strong></span>
              </div>
            )}

            <div className="modal-footer-row" style={{ marginTop: "24px" }}>
              <button className="primary-btn" onClick={() => setPrivacyModalOpen(false)}>
                Understood & Verified
              </button>
              {result && (
                <button
                  className="burn-action-btn"
                  onClick={() => {
                    setPrivacyModalOpen(false);
                    burnSession(false);
                  }}
                >
                  🔥 Burn My Data Now
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ====================================================================
          FOOTER
          ==================================================================== */}
      <footer className="site-footer" id="about-section">
        <div className="footer-container">
          <div className="footer-top-row">
            <div className="brand-link" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
              <div className="brand-logo-badge" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="12" cy="12" r="10" stroke="white" strokeWidth="1.6" strokeOpacity="0.4" />
                  <path d="M12 4C12 4 17 8 17 12C17 14.7614 14.7614 17 12 17C9.23858 17 7 14.7614 7 12C7 8 12 4 12 4Z" fill="white" />
                  <circle cx="12" cy="12" r="2.5" fill="#006241" />
                </svg>
              </div>
              <div className="brand-text">
                <span className="brand-name">{t.brand}</span>
                <span className="brand-subtitle">Your data. Clear answers. Better decisions.</span>
              </div>
            </div>

            <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", fontSize: "13px" }}>
              <span className="nav-item" onClick={() => scrollToSection("upload-section")}>
                Explore Data
              </span>
              <span className="nav-item" onClick={() => scrollToSection("samples-section")}>
                Sample Datasets
              </span>
              <span className="nav-item" onClick={() => scrollToSection("features-section")}>
                Features
              </span>
              <span className="nav-item" onClick={() => scrollToSection("how-it-works-section")}>
                How It Works
              </span>
            </div>
          </div>

          <div className="footer-bottom-row">
            <span>© OmniLens Platform. Universal Data Intelligence. All processing remains secure in session.</span>
            <span>Starbucks-Inspired Premium Warm Aesthetic</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
