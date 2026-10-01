# 16 — Complete Interview Workflow (End-to-End)

## Human-Readable Flow

1. Candidate opens browser and fills in their name + difficulty level
2. Browser establishes WebSocket to /ws/interview
3. Server creates session record in PostgreSQL and initialises the BKT graph
4. Gemini Live connects; Alex greets the candidate by name and asks them to introduce themselves
5. Candidate speaks; browser captures audio and streams PCM to server
6. Server forwards PCM to Gemini Live which transcribes it
7. Candidate finishes speaking; browser sends mic_stop / end_of_speech
8. Server consolidates transcript and fires Shadow Evaluator in background
9. Server constructs Socratic prompt payload and sends to Gemini Live
10. Alex responds (voice); server streams audio back to browser
11. Shadow Evaluator result updates BKT, MIRT, PolicyRouter, Proctor
12. Real-time telemetry broadcast to browser
13. Turn persisted to PostgreSQL
14. After INTRO turn: vector search maps introduction to competency pillars
15. Knowledge graph built from matched pillars; active topic selected
16. For each topic: max 3 turns or mastery >= 0.80
17. Devil's Advocate triggered if sudden mastery surge
18. On topic completion: compacted card saved; graph propagates mastery
19. When all topics done: session wraps up
20. Reports generated (Student + Evaluator) and archived to PostgreSQL

---

## Technical Sequence with File References

```
Browser -> WebSocket connect (ws://host/ws/interview)
    live_server.py: websocket_interview()
    -> websocket.receive_json()  [init_data]
    -> session_id = uuid4 hex
    -> db_service.create_session()  [PostgreSQL INSERT]
    -> PolicyRouter(seniority=tier)  [policy_router.py]
    -> policy_router.initialize_session(initial_skills)
    -> ACTIVE_SESSIONS[session_id] = {...}

Gemini Live connect
    live_server.py: client.aio.live.connect(model, config)
    -> build_live_config(): system prompt + speech config + STT config + compression
    -> asyncio.create_task(gemini_receive_loop())
    -> asyncio.create_task(mic_forward_loop())
    -> asyncio.create_task(_log_diag_stats())
    -> session.send_client_content(greeting_prompt)
    -> wait alex_turn_complete_event

Turn Loop:
    Browser sends binary PCM
    -> _mic_queue.put_nowait(raw_bytes)
    -> mic_forward_loop: session.send_realtime_input(audio=Blob PCM)
    -> Gemini Live: STT -> input_transcription events
    -> candidate_transcript_buffer += chunk

    Browser sends end_of_speech
    -> session.send_realtime_input(activity_end)
    -> trailing wait 1.0s for STT stability
    -> user_text = candidate_transcript_buffer.strip()
    -> transcript validation (length, language)
    -> asyncio.create_task(run_shadow_pipeline(user_text, alex_latest_question))

    Shadow Pipeline (background):
        evaluator_engine.evaluate_candidate_response()  [Gemini REST, 6.5s timeout]
        -> obs, depth_score, estimated_difficulty, rubric_items
        policy_router.process_candidate_turn(obs, latency_ms, transcript, estimated_difficulty)
            -> proctor_engine.record_turn()  [TTR, latency jitter, flags]
            -> bkt_engine.BKTNode.update(obs, scaffolding_level)  [Bayesian posterior]
            -> mirt_engine.update_ability(item, obs)  [5D gradient update]
            -> FSM transition: SCAFFOLD / DEEPEN / DEVILS_ADVOCATE / NEXT_SKILL / CONCLUDE
        -> db_service.log_turn_telemetry()  [PostgreSQL INSERT]
        -> broadcast_telemetry()  [WebSocket JSON to browser]

    Prompt construction (session_phase = INTRO or DEEP_DIVE or WRAPPING_UP)
        INTRO:
            vector_service.match_candidate_topics()  [DynamoDB vector search]
            ecosystem_service.detect_ecosystems_from_intro()
            ecosystem_service.bind_pillars_to_ecosystems()
            graph_engine.build_dynamic_pillar_graph()
            policy_router.initialize_session(custom_graph=dynamic_graph)
            db_service.update_session_blueprint()  [PostgreSQL UPDATE]
            session_phase = "DEEP_DIVE"
        DEEP_DIVE:
            if mastery >= 0.80 or turns >= 3:
                graph_engine.propagate_mastery()
                db_service.save_compacted_topic_card()
                policy_router.graph.get_next_recommended_skill()
                if next_skill: transition topic
                else: session_phase = "WRAPPING_UP"
            eco_directive = ecosystem_service.get_ecosystem_directive()
            prompt_payload = candidate answer + offtopic_guard + pedagogical + eco_directive

    session.send_client_content(prompt_payload)
    -> Alex (Gemini Live) generates response
    -> gemini_receive_loop streams audio + transcript to browser
    -> alex_turn_complete_event.set()

Finish:
    Browser sends finish_interview event (or REST POST /finish)
    -> generate_student_report()  [report_generator.py, Gemini REST]
    -> generate_evaluator_report()  [report_generator.py, template]
    -> db_service.save_final_reports()  [PostgreSQL UPSERT]
    -> WebSocket event: reports_generated {student_report, evaluator_report}

Disconnect:
    WebSocketDisconnect -> finally block
    -> SESSION_CACHE snapshot preserved
    -> if turns_history > 0 and no existing report:
        asyncio.create_task(_auto_generate_and_save_reports())
    -> ACTIVE_SESSIONS.pop(session_id)
```
