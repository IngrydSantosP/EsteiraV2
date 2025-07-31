const mongoose = require('mongoose');

// Definindo o schema para Experiência
const experienciaSchema = new mongoose.Schema({
  empresa: String,
  cargo: String,
  dataInicio: Date,
  dataSaida: Date,
  atualmente: Boolean,
});

// Definindo o schema para Competência
const competenciaSchema = new mongoose.Schema({
  nome: String,
  nivel: String, // Exemplo: "Básico", "Intermediário", "Avançado"
});

// Definindo o UserSchema
const userSchema = new mongoose.Schema({
  nome: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  senha: { type: String, required: true },
  telefone: String,
  linkedin: String,
  pretensaoSalarial: Number,
  experiencias: [experienciaSchema],  // Agora usando o esquema de Experiência
  competencias: [competenciaSchema],  // Agora usando o esquema de Competência
});

// Exportando o modelo User
module.exports = mongoose.model('User', userSchema);
