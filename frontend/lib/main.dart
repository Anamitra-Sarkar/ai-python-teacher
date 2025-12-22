import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const AiPythonTeacherApp());
}

class AiPythonTeacherApp extends StatelessWidget {
  const AiPythonTeacherApp({super.key});

  @override
  Widget build(BuildContext context) {
    final baseTheme = ThemeData.dark(useMaterial3: true);
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'AI-Assisted Python Learning',
      theme: baseTheme.copyWith(
        colorScheme: baseTheme.colorScheme.copyWith(
          primary: const Color(0xFF7C4DFF),
          secondary: const Color(0xFF00BFA5),
          surface: const Color(0xFF121212),
        ),
        scaffoldBackgroundColor: const Color(0xFF0F0F12),
        cardColor: const Color(0xFF17171C),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
          isDense: true,
        ),
      ),
      home: const HomePage(),
    );
  }
}

enum ChatRole { user, tutor, system }

class ChatMessage {
  final ChatRole role;
  final String text;

  ChatMessage(this.role, this.text);
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final _http = http.Client();

  final _backendUrlController = TextEditingController(
    text: 'http://127.0.0.1:5000/ask-ai',
  );

  final _topicController = TextEditingController(text: 'Lists / Loops');
  final _codeController = TextEditingController(
    text: '''
# Write Python here
nums = [1, 2, 3]
for i in range(len(nums)):
    print(nums[i])
'''.trim(),
  );
  final _questionController = TextEditingController(
    text: 'How can I write this more "Pythonic", and why is that better?',
  );

  String _level = 'beginner';
  bool _loading = false;

  final List<ChatMessage> _messages = <ChatMessage>[
    ChatMessage(
      ChatRole.system,
      'Tutor is ready. Ask a question about your code, an error message, or a concept.',
    ),
  ];

  @override
  void dispose() {
    _http.close();
    _backendUrlController.dispose();
    _topicController.dispose();
    _code_controller_dispose();
    _questionController.dispose();
    super.dispose();
  }

  void _code_controller_dispose() => _codeController.dispose();

  Future<Map<String, dynamic>> _postJsonWithRetry(
    Uri url,
    Map<String, dynamic> payload,
  ) async {
    final delays = <Duration>[
      Duration.zero,
      const Duration(seconds: 1),
      const Duration(seconds: 2),
      const Duration(seconds: 4),
    ];

    Object? lastError;

    for (var i = 0; i < delays.length; i++) {
      if (delays[i] != Duration.zero) {
        await Future<void>.delayed(delays[i]);
      }

      try {
        final resp = await _http
            .post(
              url,
              headers: const {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
              },
              body: jsonEncode(payload),
            )
            .timeout(const Duration(seconds: 25));

        if (resp.statusCode >= 200 && resp.statusCode < 300) {
          final decoded = jsonDecode(resp.body);
          if (decoded is Map<String, dynamic>) return decoded;
          throw const FormatException('Response JSON was not an object.');
        }

        final shouldRetry = resp.statusCode == 429 ||
            resp.statusCode == 500 ||
            resp.statusCode == 502 ||
            resp.statusCode == 503 ||
            resp.statusCode == 504;

        if (!shouldRetry) {
          throw HttpException(
            'Backend error ${resp.statusCode}: ${resp.body}',
            uri: url,
          );
        }

        lastError = HttpException(
          'Transient backend error ${resp.statusCode}: ${resp.body}',
          uri: url,
        );
      } on TimeoutException catch (e) {
        lastError = e;
      } on FormatException {
        rethrow;
      } catch (e) {
        lastError = e;
      }
    }

    throw lastError ?? Exception('Unknown request failure.');
  }

  Future<void> _askTutor() async {
    final backendUrl = _backendUrlController.text.trim();
    final question = _questionController.text.trim();

    if (backendUrl.isEmpty) {
      _append(ChatRole.system, 'Backend URL is empty.');
      return;
    }
    if (question.isEmpty) {
      _append(ChatRole.system, 'Please type a question.');
      return;
    }

    Uri url;
    try {
      url = Uri.parse(backendUrl);
      if (!url.hasScheme) {
        _append(ChatRole.system, 'Backend URL must include http:// or https://');
        return;
      }
    } catch (_) {
      _append(ChatRole.system, 'Backend URL is not a valid URI.');
      return;
    }

    final payload = <String, dynamic>{
      'topic': _topicController.text.trim(),
      'code': _code_controller_text_safe(),
      'question': question,
      'level': _level,
    };

    setState(() {
      _loading = true;
      _messages.add(ChatMessage(ChatRole.user, question));
      _questionController.clear();
    });

    try {
      final data = await _postJsonWithRetry(url, payload);
      final answer = (data['answer'] ?? '').toString().trim();
      if (answer.isEmpty) {
        _append(ChatRole.system, 'Tutor returned an empty response.');
      } else {
        _append(ChatRole.tutor, answer);
      }
    } catch (e) {
      _append(
        ChatRole.system,
        'Request failed: $e\n\nTip: if you are on an Android emulator, try http://10.0.2.2:5000/ask-ai',
      );
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  String _code_controller_text_safe() {
    final text = _codeController.text;
    if (text.length > 100000) {
      return text.substring(0, 100000) + '\n# [truncated by client]';
    }
    return text;
  }

  void _append(ChatRole role, String text) {
    setState(() => _messages.add(ChatMessage(role, text)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI-Assisted Python Learning'),
        actions: [
          IconButton(
            tooltip: 'Send to Tutor',
            onPressed: _loading ? null : _askTutor,
            icon: const Icon(Icons.send),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Row(
        children: [
          Expanded(
            flex: 7,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                children: [
                  _buildControls(context),
                  const SizedBox(height: 12),
                  Expanded(
                    child: Card(
                      clipBehavior: Clip.antiAlias,
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: TextField(
                          controller: _codeController,
                          expands: true,
                          maxLines: null,
                          minLines: null,
                          keyboardType: TextInputType.multiline,
                          style: const TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 14,
                            height: 1.35,
                          ),
                          decoration: const InputDecoration(
                            labelText: 'Python Code',
                            alignLabelWithHint: true,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          SizedBox(
            width: 420,
            child: Container(
              decoration: BoxDecoration(
                color: Theme.of(context).cardColor,
                border: Border(
                  left: BorderSide(
                    color: Colors.white.withOpacity(0.08),
                    width: 1,
                  ),
                ),
              ),
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
                    child: Row(
                      children: [
                        const Expanded(
                          child: Text(
                            'AI Tutor',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                          ),
                        ),
                        if (_loading)
                          const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                      ],
                    ),
                  ),
                  const Divider(height: 1),
                  Expanded(child: _buildChatList()),
                  const Divider(height: 1),
                  _buildComposer(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildControls(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _backendUrlController,
                    decoration: const InputDecoration(
                      labelText: 'Backend URL',
                      hintText: 'http://127.0.0.1:5000/ask-ai',
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                SizedBox(
                  width: 180,
                  child: DropdownButtonFormField<String>(
                    value: _level,
                    items: const [
                      DropdownMenuItem(value: 'beginner', child: Text('Beginner')),
                      DropdownMenuItem(value: 'intermediate', child: Text('Intermediate')),
                      DropdownMenuItem(value: 'advanced', child: Text('Advanced')),
                    ],
                    onChanged: (v) => setState(() => _level = v ?? 'beginner'),
                    decoration: const InputDecoration(labelText: 'Level'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _topicController,
              decoration: const InputDecoration(
                labelText: 'Topic (optional)',
                hintText: 'e.g., Exceptions, Functions, OOP, List Comprehensions',
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChatList() {
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _messages.length,
      itemBuilder: (context, idx) {
        final m = _messages[idx];
        final isUser = m.role == ChatRole.user;

        Color bubbleColor;
        Alignment align;
        IconData icon;

        switch (m.role) {
          case ChatRole.user:
            bubbleColor = Theme.of(context).colorScheme.primary.withOpacity(0.25);
            align = Alignment.centerRight;
            icon = Icons.person;
            break;
          case ChatRole.tutor:
            bubbleColor = Theme.of(context).colorScheme.secondary.withOpacity(0.20);
            align = Alignment.centerLeft;
            icon = Icons.school;
            break;
          case ChatRole.system:
            bubbleColor = Colors.white.withOpacity(0.08);
            align = Alignment.centerLeft;
            icon = Icons.info_outline;
            break;
        }

        return Align(
          alignment: align,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 380),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: bubbleColor,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white.withOpacity(0.08)),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Icon(icon, size: 16, color: Colors.white.withOpacity(0.85)),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: SelectableText(
                          m.text,
                          style: TextStyle(
                            height: 1.35,
                            color: isUser ? Colors.white : Colors.white.withOpacity(0.92),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildComposer() {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _questionController,
              enabled: !_loading,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _loading ? null : _askTutor(),
              decoration: const InputDecoration(
                labelText: 'Ask the Tutor',
                hintText: 'Paste an error message or ask about a specific line...',
              ),
            ),
          ),
          const SizedBox(width: 10),
          FilledButton(
            onPressed: _loading ? null : _askTutor,
            child: const Text('Send'),
          ),
        ],
      ),
    );
  }
}

class HttpException implements Exception {
  final String message;
  final Uri? uri;

  const HttpException(this.message, {this.uri});

  @override
  String toString() => uri == null ? message : '$message (uri: $uri)';
}
