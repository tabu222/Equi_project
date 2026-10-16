import { useEffect, useRef, useState } from 'react'
import { registerOwner } from '../../api/registrationApi.js'
import { getClubs } from '../../api/horseApi.ts'
import { Link } from 'react-router-dom'
import './LoginScreen.css'

function Field({ label, name, type = 'text', value, onChange, autoComplete, minLength, maxLength, children }) {
  return <label className="auth-field">
    <span>{label}</span>
    <span className="auth-input-wrap">
      <input name={name} type={type} value={value} onChange={onChange} autoComplete={autoComplete} minLength={minLength} maxLength={maxLength} required />
      {children}
    </span>
  </label>
}

function PasswordField(props) {
  const [visible, setVisible] = useState(false)
  return <Field {...props} type={visible ? 'text' : 'password'}>
    <button type="button" className="auth-reveal" aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'} aria-pressed={visible} onClick={() => setVisible(!visible)}>
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" />{visible && <path d="m3 3 18 18" />}</svg>
    </button>
  </Field>
}

export default function LoginScreen({ onLogin, error = '', busy = false, onRegister = registerOwner }) {
  const [mode, setMode] = useState('login')
  const [changed, setChanged] = useState(false)
  const [login, setLogin] = useState({ email: '', password: '' })
  const emptyRegistration = { fullName: '', email: '', phone: '', address: '', clubId: '', password: '', confirmPassword: '' }
  const [registration, setRegistration] = useState(emptyRegistration)
  const [clubs, setClubs] = useState([])
  const [clubsLoading, setClubsLoading] = useState(false)
  const [clubsError, setClubsError] = useState('')
  const [clubRetry, setClubRetry] = useState(0)
  const [formError, setFormError] = useState('')
  const [notice, setNotice] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const loginRef = useRef(null)
  const registerRef = useRef(null)
  const firstRender = useRef(true)
  const registering = mode === 'register'
  const pending = busy || submitting

  useEffect(() => {
    if (!registering) return
    let active = true
    getClubs().then((rows) => {
      if (active) { setClubs(rows); setClubsError('') }
    }).catch((cause) => {
      if (active) setClubsError(cause instanceof Error ? cause.message : 'Không thể tải câu lạc bộ.')
    }).finally(() => { if (active) setClubsLoading(false) })
    return () => { active = false }
  }, [registering, clubRetry])

  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return }
    const delay = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 1550
    const timer = window.setTimeout(() => {
      const form = registering ? registerRef.current : loginRef.current
      form?.querySelector('input')?.focus({ preventScroll: true })
    }, delay)
    return () => window.clearTimeout(timer)
  }, [registering])

  function switchMode(next) {
    if (pending) return
    setChanged(true)
    setFormError('')
    setNotice('')
    if (next === 'register') setClubsLoading(true)
    setMode(next)
  }

  const update = (setter) => (event) => {
    const { name, value } = event.target
    setter((previous) => ({ ...previous, [name]: value }))
    setFormError('')
    if (name === 'confirmPassword' || name === 'password') {
      registerRef.current?.elements.confirmPassword.setCustomValidity('')
    }
  }

  async function submitLogin(event) {
    event.preventDefault()
    if (pending) return
    setFormError('')
    setNotice('')
    setSubmitting(true)
    try { await onLogin(login.email.trim(), login.password) }
    catch (cause) { setFormError(cause instanceof Error ? cause.message : 'Không thể đăng nhập. Vui lòng thử lại.') }
    finally { setSubmitting(false) }
  }

  async function submitRegistration(event) {
    event.preventDefault()
    if (pending) return
    if (!registration.fullName.trim()) { setFormError('Vui lòng nhập họ và tên.'); return }
    if (registration.password !== registration.confirmPassword) {
      const confirm = registerRef.current.elements.confirmPassword
      confirm.setCustomValidity('Mật khẩu xác nhận chưa khớp.')
      confirm.reportValidity()
      return
    }
    setFormError('')
    setSubmitting(true)
    try {
      await onRegister({ fullName: registration.fullName.trim(), email: registration.email.trim(), phone: registration.phone.trim(), address: registration.address.trim(), clubId: registration.clubId, password: registration.password })
      setLogin({ email: registration.email.trim(), password: '' })
      setRegistration(emptyRegistration)
      setChanged(true)
      setMode('login')
      setNotice('Đăng ký thành công. Bạn có thể đăng nhập bằng tài khoản vừa tạo.')
    } catch (cause) { setFormError(cause instanceof Error ? cause.message : 'Không thể đăng ký. Vui lòng thử lại.') }
    finally { setSubmitting(false) }
  }

  return <main className="auth-page">
    <Link to="/" className="auth-brand"><span className="brand-mark" aria-hidden="true"><img src="/equitrack-mark.jpg" alt="" /></span><span><strong>EQUITRACK</strong><small>Racehorse performance</small></span></Link>
    <section className={`auth-card ${registering ? 'is-register' : 'is-login'} ${changed ? 'has-switched' : ''}`} aria-label="Tài khoản EquiTrack">
      <div className="auth-diagonal" aria-hidden="true" />
      <aside className="auth-welcome auth-welcome-login" aria-hidden={registering}>
        <span className="auth-step">EQUITRACK · CÂU LẠC BỘ</span><h2>CHÀO MỪNG<br />{' '}TRỞ LẠI!</h2><p>Đồng hành cùng bạn<br />{' '}trên mỗi chặng đường<br />{' '}phát triển của ngựa.</p><span className="auth-rule" />
      </aside>
      <aside className="auth-welcome auth-welcome-register" aria-hidden={!registering}>
        <span className="auth-step">EQUITRACK · KHỞI ĐẦU MỚI</span><h2>BẮT ĐẦU<br />{' '}CÙNG EQUITRACK.</h2><p>Kết nối câu lạc bộ.<br />{' '}Theo dõi sức khỏe.<br />{' '}Chinh phục mục tiêu.</p><span className="auth-rule" />
      </aside>
      <form ref={loginRef} className="auth-form auth-login" onSubmit={submitLogin} inert={registering} aria-hidden={registering} aria-labelledby="login-title" aria-busy={pending && !registering}>
        <div className="auth-item" style={{ '--i': 0 }}><p className="auth-kicker">TÀI KHOẢN EQUITRACK</p><h1 id="login-title">Đăng nhập</h1></div>
        <div className="auth-item" style={{ '--i': 1 }}><Field label="Email" name="email" type="email" autoComplete="username" value={login.email} onChange={update(setLogin)} maxLength={254} /></div>
        <div className="auth-item" style={{ '--i': 2 }}><PasswordField label="Mật khẩu" name="password" autoComplete="current-password" value={login.password} onChange={update(setLogin)} /></div>
        {!registering && (formError || (!changed && error)) && <p className="auth-feedback auth-error" role="alert">{formError || error}</p>}
        {!registering && notice && <p className="auth-feedback auth-success" role="status">{notice}</p>}
        <button className="auth-submit auth-item" style={{ '--i': 3 }} type="submit" disabled={pending}>{pending && !registering ? 'Đang đăng nhập…' : 'Đăng nhập'}<span aria-hidden="true">→</span></button>
        <p className="auth-switch auth-item" style={{ '--i': 4 }}>Chưa có tài khoản? <button type="button" onClick={() => switchMode('register')} disabled={pending}>Đăng ký</button></p>
      </form>
      <form ref={registerRef} className="auth-form auth-register" onSubmit={submitRegistration} inert={!registering} aria-hidden={!registering} aria-labelledby="register-title" aria-busy={pending && registering}>
        <div className="auth-item" style={{ '--i': 0 }}><p className="auth-kicker">GIA NHẬP EQUITRACK</p><h1 id="register-title">Đăng ký</h1></div>
        <div className="auth-item" style={{ '--i': 1 }}><Field label="Họ và tên" name="fullName" autoComplete="name" value={registration.fullName} onChange={update(setRegistration)} maxLength={150} /></div>
        <div className="auth-item" style={{ '--i': 2 }}><Field label="Email" name="email" type="email" autoComplete="email" value={registration.email} onChange={update(setRegistration)} maxLength={254} /></div>
        <div className="auth-item" style={{ '--i': 3 }}><Field label="Số điện thoại" name="phone" type="tel" autoComplete="tel" value={registration.phone} onChange={update(setRegistration)} maxLength={20} /></div>
        <div className="auth-item" style={{ '--i': 4 }}><Field label="Địa chỉ" name="address" autoComplete="street-address" value={registration.address} onChange={update(setRegistration)} maxLength={255} /></div>
        <div className="auth-item" style={{ '--i': 5 }}><label className="auth-field"><span>Câu lạc bộ</span><select required name="clubId" value={registration.clubId} onChange={update(setRegistration)} disabled={clubsLoading || Boolean(clubsError)}><option value="">{clubsLoading ? 'Đang tải…' : 'Chọn câu lạc bộ'}</option>{clubs.map((club) => <option key={club.id} value={club.id}>{club.name}</option>)}</select></label></div>
        {registering && clubsError && <p className="auth-feedback auth-error" role="alert">{clubsError} <button type="button" disabled={clubsLoading} onClick={() => { setClubsLoading(true); setClubRetry((count) => count + 1) }}>Thử lại</button></p>}
        {registering && !clubsLoading && !clubsError && clubs.length === 0 && <p className="auth-feedback" role="status">Chưa có CLB đang hoạt động để đăng ký.</p>}
        <div className="auth-item" style={{ '--i': 6 }}><PasswordField label="Mật khẩu (ít nhất 6 ký tự)" name="password" autoComplete="new-password" value={registration.password} onChange={update(setRegistration)} minLength={6} /></div>
        <div className="auth-item" style={{ '--i': 7 }}><PasswordField label="Xác nhận mật khẩu" name="confirmPassword" autoComplete="new-password" value={registration.confirmPassword} onChange={update(setRegistration)} minLength={6} /></div>
        {registering && formError && <p className="auth-feedback auth-error" role="alert">{formError}</p>}
        <button className="auth-submit auth-item" style={{ '--i': 8 }} type="submit" disabled={pending || clubsLoading || Boolean(clubsError) || clubs.length === 0}>{pending && registering ? 'Đang đăng ký…' : 'Tạo tài khoản'}<span aria-hidden="true">→</span></button>
        <p className="auth-switch auth-item" style={{ '--i': 9 }}>Đã có tài khoản? <button type="button" onClick={() => switchMode('login')} disabled={pending}>Đăng nhập</button></p>
      </form>
    </section>
    <footer className="auth-footer">EQUITRACK<span aria-hidden="true"> / </span>Chăm sóc hôm nay. Vững bước ngày mai.</footer>
  </main>
}
