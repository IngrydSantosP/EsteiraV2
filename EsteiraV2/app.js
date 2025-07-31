require('dotenv').config()
const express = require('express')
const mongoose = require('mongoose')
const bcrypt = require('bcrypt')
const jwt = require('jsonwebtoken')
const cors = require('cors')

const app = express()

// Configurar JSON e CORS
app.use(express.json())
app.use(cors())

// Importação do modelo User
const User = require('./models/User')

// Middleware para checar token JWT
function checkToken(req, res, next) {
  const authHeader = req.headers['authorization']
  const token = authHeader && authHeader.split(" ")[1]

  if (!token) {
    return res.status(401).json({ msg: 'Acesso negado!' })
  }

  try {
    const secret = process.env.SECRET
    jwt.verify(token, secret)
    next()
  } catch (error) {
    return res.status(400).json({ msg: 'Token inválido!' })
  }
}

// Rota pública
app.get('/', (req, res) => {
  res.status(200).json({ msg: 'Bem vindo à nossa API' })
})

// Rota privada - obter dados do usuário (sem a senha)
app.get('/user/:id', checkToken, async (req, res) => {
  const id = req.params.id

  try {
    const user = await User.findById(id, '-senha')
    if (!user) {
      return res.status(404).json({ msg: 'Usuário não encontrado' })
    }
    res.status(200).json({ user })
  } catch (error) {
    res.status(500).json({ msg: 'Erro ao buscar usuário' })
  }
})

// Rota para atualizar perfil do usuário
app.put('/user/:id', checkToken, async (req, res) => {
  const id = req.params.id
  const {
    telefone,
    linkedin,
    pretensaoSalarial,
    experiencias,
    competencias
  } = req.body

  try {
    const updatedUser = await User.findByIdAndUpdate(
      id,
      {
        telefone,
        linkedin,
        pretensaoSalarial,
        experiencias,
        competencias
      },
      { new: true, runValidators: true }
    ).select('-senha')

    if (!updatedUser) {
      return res.status(404).json({ msg: 'Usuário não encontrado para atualização' })
    }

    res.status(200).json({ msg: 'Perfil atualizado com sucesso!', user: updatedUser })
  } catch (error) {
    res.status(500).json({ msg: 'Erro ao atualizar perfil', error })
  }
})

// Registro de usuário
app.post('/auth/register', async (req, res) => {
  const { nome, email, senha, confirmar_senha } = req.body

  // Validações
  if (!nome) return res.status(422).json({ msg: 'O nome é obrigatório!' })
  if (!email) return res.status(422).json({ msg: 'O email é obrigatório!' })
  if (!senha) return res.status(422).json({ msg: 'A senha é obrigatória!' })
  if (senha !== confirmar_senha) return res.status(422).json({ msg: 'As senhas não estão iguais!' })

  // Verifica se email já está cadastrado
  const userExists = await User.findOne({ email: email })
  if (userExists) return res.status(422).json({ msg: 'Por favor, digite outro email!' })

  // Cria hash da senha
  const salt = await bcrypt.genSalt(12)
  const passwordHash = await bcrypt.hash(senha, salt)

  // Cria usuário
  const user = new User({
    nome,
    email,
    senha: passwordHash,
  })

  try {
    await user.save()
    res.status(201).json({ msg: 'Usuário criado com sucesso!' })
  } catch (error) {
    console.log(error)
    res.status(500).json({ msg: 'Erro no servidor, tente novamente mais tarde' })
  }
})

// Login
app.post('/auth/login', async (req, res) => {
  const { email, senha } = req.body

  if (!email) return res.status(422).json({ msg: 'O email é obrigatório!' })
  if (!senha) return res.status(422).json({ msg: 'A senha é obrigatória!' })

  const user = await User.findOne({ email: email })
  if (!user) return res.status(404).json({ msg: 'Usuário não encontrado!' })

  const checkPassword = await bcrypt.compare(senha, user.senha)
  if (!checkPassword) return res.status(422).json({ msg: 'Senha inválida!' })

  try {
    const secret = process.env.SECRET
    const token = jwt.sign({ id: user._id }, secret)

    // Opcional: retornar também dados básicos do usuário junto com o token
    const { nome, telefone, linkedin, pretensaoSalarial, experiencias, competencias } = user

    res.status(200).json({
      msg: 'Autenticação realizada com sucesso!',
      token,
      user: { nome, email, telefone, linkedin, pretensaoSalarial, experiencias, competencias }
    })
  } catch (error) {
    console.log(error)
    res.status(500).json({ msg: 'Erro no servidor, tente novamente mais tarde' })
  }
})

// Credenciais para conexão com o MongoDB
const dbUser = process.env.DB_USER
const dbPassword = process.env.DB_PASS

mongoose.connect(
  `mongodb+srv://${dbUser}:${dbPassword}@oh14g0.khedpdf.mongodb.net/?retryWrites=true&w=majority&appName=oh14g0`
)
.then(() => {
  console.log('Conectou ao banco!')
  app.listen(3000, () => console.log('Servidor rodando na porta 3000'))
})
.catch((err) => console.log('Erro ao conectar ao MongoDB:', err))
