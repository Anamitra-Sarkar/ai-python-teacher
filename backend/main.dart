import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

void main() {
  runApp(const PythonTutorApp());
}

class PythonTutorApp extends StatelessWidget {
  const PythonTutorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PyTutor Pro AI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        primarySwatch: Colors.yellow,
        scaffoldBackgroundColor: const Color(0xFF0F172A),
        cardColor: const Color(0xFF1E293B),
        fontFamily: 'JetBrainsMono', // Using monospaced font feel
      ),
      home: const TutorHomeScreen(),
    );
  }
}

class Lesson {
  final String title;
  final String content;
  final String starterCode;
  final String goal;

  Lesson({
    required this.title,
    required this.content,
    required this.starterCode,
    required this.goal,
  });
}

class TutorHomeScreen extends StatefulWidget {
  const TutorHomeScreen({super.key});

  @override
  State<TutorHomeScreen> createState() => _TutorHomeScreenState();
}

class _TutorHomeScreenState extends State<TutorHomeScreen> {
  // Configuration
  final String backendUrl = "http://localhost:5000/ask-ai"; // Update for your IP
  
  // App State
  final List<Lesson> _lessons = [
    Lesson(
      title: "Python Variables",
      content: "Variables are containers for storing data. In Python, you create one by assigning a value.",
      starterCode: "name = 'Alex'\nprint(name)",
      goal: "Assign your name to a variable and print it.",
    ),
    Lesson(
      title: "If Statements",
      content: "Use 'if' to execute code only when a condition is true.",
      starterCode: "age = 20\nif age >= 18:\n    print('Adult')",
      goal: "Check if age is greater than 18.",
    ),
  ];

  late Lesson _activeLesson;
  late TextEditingController _codeController;
  final TextEditingController _chatController = TextEditingController();
  final List<Map<String, String>> _messages = [
    {"role": "assistant", "content": "Hi! I'm your Python Tutor. Stuck on this lesson? Ask me anything!"}
  ];
  
  String _userLevel = "Beginner";
  bool _isLoading = false;
  bool _isChatVisible = true;

  @override
  void initState() {
    super.initState();
    _activeLesson = _lessons[0];
    _codeController = TextEditingController(text: _activeLesson.starterCode);
  }

  Future<void> _sendMessage() async {
    if (_chatController.text.isEmpty) return;

    String userQuery = _chatController.text;
    setState(() {
      _messages.add({"role": "user", "content": userQuery});
      _isLoading = true;
    });
    _chatController.clear();

    try {
      final response = await http.post(
        Uri.parse(backendUrl),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "topic": _activeLesson.title,
          "code": _codeController.text,
          "question": userQuery,
          "level": _userLevel,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _messages.add({"role": "assistant", "content": data['answer']});
        });
      } else {
        _showError("Failed to connect to AI server.");
      }
    } catch (e) {
      _showError("Backend offline. Run app.py first!");
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void _showError(String msg) {
    setState(() {
      _messages.add({"role": "assistant", "content": "⚠️ Error: $msg"});
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F172A),
        elevation: 0,
        title: const Text("PyTutor Pro AI", style: TextStyle(fontWeight: FontWeight.bold, color: Colors.yellow)),
        actions: [
          DropdownButton<String>(
            value: _userLevel,
            dropdownColor: const Color(0xFF1E293B),
            underline: Container(),
            items: ["Beginner", "Intermediate", "Advanced"].map((String value) {
              return DropdownMenuItem<String>(value: value, child: Text(value, style: const TextStyle(fontSize: 12)));
            }).toList(),
            onChanged: (val) => setState(() => _userLevel = val!),
          ),
          IconButton(
            icon: Icon(_isChatVisible ? Icons.chat_bubble : Icons.chat_bubble_outline),
            onPressed: () => setState(() => _isChatVisible = !_isChatVisible),
          ),
        ],
      ),
      body: Row(
        children: [
          // Main Content Area
          Expanded(
            flex: 3,
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Lesson Tabs
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: _lessons.map((l) => Padding(
                        padding: const EdgeInsets.only(right: 8.0),
                        child: ChoiceChip(
                          label: Text(l.title),
                          selected: _activeLesson == l,
                          onSelected: (s) {
                            setState(() {
                              _activeLesson = l;
                              _codeController.text = l.starterCode;
                            });
                          },
                        ),
                      )).toList(),
                    ),
                  ),
                  const SizedBox(height: 24),
                  // Lesson Card
                  Card(
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    child: Padding(
                      padding: const EdgeInsets.all(20.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(_activeLesson.title, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                          const SizedBox(height: 12),
                          Text(_activeLesson.content, style: const TextStyle(color: Colors.white70)),
                          const SizedBox(height: 16),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(color: Colors.blue.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
                            child: Row(
                              children: [
                                const Icon(Icons.lightbulb, color: Colors.blue, size: 20),
                                const SizedBox(width: 10),
                                Expanded(child: Text("Goal: ${_activeLesson.goal}", style: const TextStyle(fontSize: 13, color: Colors.blue))),
                              ],
                            ),
                          )
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  // Editor Header
                  Row(
                    children: const [
                      Icon(Icons.terminal, size: 16, color: Colors.grey),
                      SizedBox(width: 8),
                      Text("MAIN.PY", style: TextStyle(color: Colors.grey, fontSize: 12, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const SizedBox(height: 8),
                  // Code Editor Simulation
                  Container(
                    decoration: BoxDecoration(
                      color: Colors.black,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Colors.white10),
                    ),
                    padding: const EdgeInsets.all(16),
                    child: TextField(
                      controller: _codeController,
                      maxLines: 10,
                      style: const TextStyle(color: Colors.greenAccent, fontFamily: 'monospace'),
                      decoration: const InputDecoration(border: InputBorder.none),
                    ),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () {},
                    icon: const Icon(Icons.play_arrow),
                    label: const Text("Run Python Code"),
                    style: ElevatedButton.styleFrom(backgroundColor: Colors.yellow, foregroundColor: Colors.black),
                  )
                ],
              ),
            ),
          ),
          
          // Sidebar AI Tutor
          if (_isChatVisible)
            Container(
              width: 350,
              decoration: const BoxDecoration(
                color: Color(0xFF1E293B),
                border: Border(left: BorderSide(color: Colors.white10)),
              ),
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    color: Colors.black26,
                    child: Row(
                      children: [
                        const CircleAvatar(backgroundColor: Colors.indigo, child: Icon(Icons.smart_toy, color: Colors.white)),
                        const SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: const [
                            Text("AI Sidebar Tutor", style: TextStyle(fontWeight: FontWeight.bold)),
                            Text("Online", style: TextStyle(fontSize: 10, color: Colors.greenAccent)),
                          ],
                        )
                      ],
                    ),
                  ),
                  Expanded(
                    child: ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _messages.length,
                      itemBuilder: (context, index) {
                        bool isUser = _messages[index]["role"] == "user";
                        return Align(
                          alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                          child: Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: isUser ? Colors.yellow : Colors.white.withOpacity(0.05),
                              borderRadius: BorderRadius.only(
                                topLeft: const Radius.circular(12),
                                topRight: const Radius.circular(12),
                                bottomLeft: isUser ? const Radius.circular(12) : Radius.zero,
                                bottomRight: isUser ? Radius.zero : const Radius.circular(12),
                              ),
                            ),
                            child: Text(
                              _messages[index]["content"]!,
                              style: TextStyle(color: isUser ? Colors.black : Colors.white, fontSize: 13),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  if (_isLoading) const LinearProgressIndicator(backgroundColor: Colors.transparent, color: Colors.yellow),
                  Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _chatController,
                            decoration: InputDecoration(
                              hintText: "Ask about code...",
                              filled: true,
                              fillColor: Colors.black26,
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                              contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                            ),
                            onSubmitted: (_) => _sendMessage(),
                          ),
                        ),
                        const SizedBox(width: 8),
                        IconButton(
                          onPressed: _sendMessage,
                          icon: const Icon(Icons.send, color: Colors.yellow),
                        )
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}