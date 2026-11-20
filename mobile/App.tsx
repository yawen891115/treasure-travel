import React, { useRef, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { Alert, KeyboardAvoidingView, Linking, Platform, Pressable, SafeAreaView, ScrollView, Share, StyleSheet, Text, TextInput, View } from 'react-native';
import { Plan, TravelAPI } from './src/api';

const BASE = process.env.EXPO_PUBLIC_API_URL || '';
const PRIVACY = process.env.EXPO_PUBLIC_PRIVACY_URL || '';
export default function App() {
  const api = useRef<TravelAPI | null>(null);
  const gate = useRef(false);
  const [ready,setReady] = useState(false), [signed,setSigned] = useState(false), [paidAccess,setPaidAccess] = useState(false), [busy,setBusy] = useState(false);
  const [username,setUsername] = useState(''), [password,setPassword] = useState('');
  const [message,setMessage] = useState(''), [plan,setPlan] = useState<Plan | null>(null), [error,setError] = useState('');
  const [consent,setConsent] = useState(false);
  async function act(fn:()=>Promise<void>) {
    if (gate.current) return;
    gate.current=true; setBusy(true); setError('');
    try { await fn(); } catch(e) { setError(e instanceof Error ? e.message : 'Something went wrong.'); }
    finally { gate.current=false;setBusy(false); }
  }
  function Button({label,onPress,disabled=false}:{label:string;onPress:()=>void;disabled?:boolean}) {
    return <Pressable accessibilityRole="button" disabled={busy||disabled} onPress={onPress} style={[s.button,(busy||disabled)&&s.disabled]}><Text style={s.buttonText}>{label}</Text></Pressable>;
  }
  const connect=()=>act(async()=>{ if(!BASE) throw new Error('This build has no server configured.'); api.current=new TravelAPI(BASE,fetch,__DEV__); const state=await api.current.session(); setSigned(state.authenticated);setPaidAccess(state.paid_access);setReady(true); });
  function confirmReset() {
    const title = 'Start again?';
    const detail = 'This clears the current planning session, not server logs.';
    const reset = () => act(async () => {
      await api.current!.reset();
      setPlan(null);
      setMessage('');
      const state = await api.current!.session();
      setSigned(state.authenticated);
      setPaidAccess(state.paid_access);
    });
    if (Platform.OS === 'web') {
      if (globalThis.confirm(`${title}\n\n${detail}`)) void reset();
      return;
    }
    Alert.alert(title, detail, [{ text: 'Cancel', style: 'cancel' }, { text: 'Start again', onPress: reset }]);
  }
  return <SafeAreaView style={s.safe}><StatusBar style="dark"/><KeyboardAvoidingView style={s.fill} behavior={Platform.OS==='ios'?'padding':undefined}><ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
    <Text style={s.eyebrow}>BOSTON · YOUR DAY, WELL PLANNED</Text><Text style={s.title}>Treasure Travel</Text><Text style={s.subtitle}>A little curiosity. A better day out.</Text>
    <View style={s.notice}><Text>Development preview. Live availability is not guaranteed. Costs are estimates; confirm important details with each venue.</Text></View>
    {!ready ? <View style={s.card}><Text style={s.heading}>Before you plan</Text><Text style={s.body}>Your messages and trip preferences will be sent to the configured travel server. Live mode sends necessary trip details to Anthropic and Google Maps. The server may retain trip logs under its published privacy policy. Do not enter confidential information.</Text><Text style={s.body}>No device location is collected. Type a starting place yourself.</Text>
      <Pressable accessibilityRole="checkbox" accessibilityState={{checked:consent}} onPress={()=>setConsent(!consent)}><Text style={s.link}>{consent?'☑':'☐'} I understand and want to connect.</Text></Pressable>
      <Button label="Connect to trip planner" onPress={connect} disabled={!consent}/>
    </View> : <>
      {signed && <Text style={s.body}>{paidAccess?'Signed in with staff preview access.':'Signed in without paid live-data access. Ask the operator for preview access.'}</Text>}
      {!signed && <View style={s.card}><Text style={s.heading}>Preview access</Text><Text style={s.body}>Staff sign-in is required for the paid live-data preview. Public account registration is not available yet.</Text><TextInput accessibilityLabel="Username" placeholder="Username" value={username} onChangeText={setUsername} autoCapitalize="none" autoComplete="username" style={s.input}/><TextInput accessibilityLabel="Password" placeholder="Password" value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none" autoComplete="current-password" style={s.input}/><Button label="Sign in" onPress={()=>act(async()=>{const secret=password;setPassword('');const state=await api.current!.login(username,secret);setSigned(state.authenticated);setPaidAccess(state.paid_access);})}/></View>}
      <View style={s.card}><Text style={s.heading}>Where shall we go?</Text><Text style={s.body}>Include a date (YYYY-MM-DD), starting place, time, budget and interests. Live plans must be within the supported upcoming-date window.</Text><TextInput accessibilityLabel="Trip request" multiline maxLength={8000} placeholder="Tomorrow, coffee and art near Boston Common…" value={message} onChangeText={setMessage} editable={!busy} style={[s.input,s.composer]}/><Button label={busy?'Working…':'Plan my day'} disabled={!message.trim()} onPress={()=>act(async()=>{setPlan(await api.current!.chat(message));setMessage('');})}/></View>
      {plan && <View style={s.card}><Text style={s.heading}>Your itinerary</Text><Text style={s.body}>{plan.reply}</Text><Text style={s.body}>{plan.data_source?.maps_mode==='google'?'Google Maps • configured live checks (not a guarantee for every stop)':'Historical data • offline estimates'}</Text><Text style={s.body}>{plan.data_source?.cost_basis}; {plan.data_source?.travel_basis}</Text>{plan.data_source?.maps_mode==='google' && <Text style={s.warning}>Live turns are not saved. Include the full date, start, budget and preferences each time.</Text>}{plan.warnings.map((w,i)=><Text key={i} style={s.warning}>{w}</Text>)}{plan.stops.map((stop,i)=><View key={`${stop.place_id}-${i}`} style={s.stop}><Text style={s.eyebrow}>{stop.arrive} — {stop.leave}</Text><Text style={s.stopTitle}>{i+1}. {stop.name}</Text>{typeof stop.est_cost==='number' && <Text>Estimated cost: ${stop.est_cost.toFixed(2)}</Text>}</View>)}<Button label="Share itinerary" onPress={()=>act(async()=>{await Share.share({message:`Treasure Travel — estimated itinerary\n${plan.stops.map(x=>`${x.arrive}–${x.leave} ${x.name}`).join('\n')}\n${plan.warnings.join('\n')}\n${plan.data_source?.maps_mode==='google'?'Google Maps · https://maps.google.com':'Offline historical data'}\nCosts are estimates.\nConfirm venue details before travel.`});})}/></View>}
      <Button label="Start a new conversation" onPress={confirmReset}/>
      {signed&&<Button label="Sign out" onPress={()=>act(async()=>{await api.current!.logout();setSigned(false);setReady(false);setPlan(null);setUsername('');setPassword('');})}/>}
    </>}
    {!!error&&<Text accessibilityRole="alert" style={s.warning}>{error}</Text>}
    {!!PRIVACY&&<Pressable onPress={()=>act(async()=>{if(!PRIVACY.startsWith('https://'))throw new Error('Privacy policy is not configured securely.');await Linking.openURL(PRIVACY);})}><Text style={s.link}>Privacy policy</Text></Pressable>}
    <Text style={s.footer}>Preview build · Not an emergency or navigation service</Text>
  </ScrollView></KeyboardAvoidingView></SafeAreaView>;
}
const s=StyleSheet.create({safe:{flex:1,backgroundColor:'#F5F3EA'},fill:{flex:1},content:{padding:24,gap:18,paddingBottom:50},eyebrow:{fontSize:11,fontWeight:'700',letterSpacing:1.5,color:'#346456'},title:{fontSize:36,fontWeight:'800',color:'#143D32'},subtitle:{fontSize:17,color:'#5E6E65'},notice:{padding:14,backgroundColor:'#E4EBDD',borderRadius:12},card:{padding:20,backgroundColor:'white',borderRadius:20,gap:12},heading:{fontSize:22,fontWeight:'700',color:'#173E32'},body:{fontSize:16,lineHeight:24,color:'#475C51'},input:{padding:14,borderWidth:1,borderColor:'#CFD8CE',borderRadius:12,fontSize:16},composer:{minHeight:120,textAlignVertical:'top'},button:{backgroundColor:'#205C48',padding:16,borderRadius:14,alignItems:'center'},disabled:{opacity:0.45},buttonText:{fontSize:16,fontWeight:'700',color:'white'},link:{color:'#205C48',paddingVertical:12,fontSize:15},warning:{color:'#963A25',fontSize:15,lineHeight:22},stop:{borderTopWidth:1,borderColor:'#E3E8DF',paddingVertical:16,gap:8},stopTitle:{fontSize:19,fontWeight:'600'},footer:{fontSize:12,color:'#6A766D',textAlign:'center'}});
